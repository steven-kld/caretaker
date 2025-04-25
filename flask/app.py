from flask import Flask, request, jsonify, Response, session
from flask_cors import CORS
import os, base64, uuid
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv
import numpy as np
import openai
from utils.logging import LogManager
from core.faiss_matcher import FaissMatcher

APP_FOLDER = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

SESSION_STORE = {} # session_id -> {'history': [...]}
MEMORY_LIMIT = 10

log_manager = LogManager()

task_matcher = FaissMatcher(
    index_path=Path("./model/vector/task_index.faiss"),
    meta_path=Path("./model/vector/task_meta.json")
)

@app.route("/api/session/init", methods=['GET'])
def init_session():
    if not session.get('user_id'):
        session['user_id'] = str(uuid.uuid4())
    user_id = session['user_id']

    # Create a logger per session and attach it
    logger = log_manager.get_session_logger(user_id)

    if user_id in SESSION_STORE:
        del SESSION_STORE[user_id]

    SESSION_STORE[user_id] = {
        "history": [],
        "logger": logger
    }
    logger.info(f"🆕 Session initialized and logger attached for uuid {user_id}")

    return jsonify({"ok": "hello dear", "session_id": user_id})

@app.route('/api/process', methods=['POST'])
def process():
    try:
        session_id = session.get('user_id')
        if not session_id:
            return jsonify({'error': 'Missing session_id'}), 400
        
        logger = SESSION_STORE[session_id]["logger"]
        logger.start_timer()
        openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        if session_id not in SESSION_STORE:
            SESSION_STORE[session_id] = {'history': []}

        audio = request.files.get('audio')
        logger.log_time("📥 Audio received")

        if not audio or not hasattr(audio.stream, 'read'):
            return jsonify({'error': 'No valid audio file'}), 400

        raw_bytes = audio.read()
        if not raw_bytes:
            return jsonify({'error': 'Empty audio stream'}), 400

        buffer = BytesIO(raw_bytes)
        buffer.name = audio.filename
        logger.log_time("📦 Audio wrapped")

        response = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=buffer,
            response_format="verbose_json"
        )
        logger.log_time("🧠 Whisper took")

        if not response.text:
            return jsonify({'error': 'Missing text'}), 400
        
        # TODO! It locks only if not locked, then has to match and answer with exact step! LOCK -> DETAIL -> UNLOCK -> LOCK
        if "matched_task" in SESSION_STORE[session_id]:
            task_match = SESSION_STORE[session_id]["matched_task"]
            logger.log_time(f"🔒 Reusing locked task: {task_match['title']}")
            confidence = 0.0  # not relevant anymore
        else:
            task_match, confidence = task_matcher.match_task(logger, response.text, openai_client)
            logger.log_time(f"User response text: {response.text}")
            logger.info(f"Match confidence: {confidence:.4f}")

            if task_match:
                SESSION_STORE[session_id]["matched_task"] = task_match
                logger.info(f"📌 Task locked: {task_match['title']}")
                logger.log_time("task locking")
                logger.info(f"🧠 {task_match['intro'].splitlines()[0]}")
            else:
                logger.log_time("⚠️ No matching task found.")

        image_files = request.files.getlist("images")

        logger.log_time("🖼 Image encoding complete")

        with ThreadPoolExecutor() as executor:
            encoded_images = list(executor.map(
                lambda img: base64.b64encode(img.read()).decode("utf-8"),
                image_files[:5]
            ))

        vision_parts = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            }
            for b64 in encoded_images
        ]

        mp3_data = generate_response(
            openai_client,
            response.text,
            vision_parts,
            session_id,
            logger,
            matched_task=task_match
        )
        logger.log_time("🤖 GPT + TTS")
        if not mp3_data:
            return jsonify({'error': 'TTS failed'}), 500

        return Response(mp3_data, mimetype="audio/mpeg")

    except Exception as e:
        logger.error("❌ Whisper failed:", e)
        return jsonify({'error': str(e)}), 500

def generate_speech(openai_client, text, voice="nova"):
    try:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        return response.content

    except Exception as e:
        print("❌ TTS failed:", e)
        return None

def generate_response(openai_client, text, vision_parts, session_id, logger, matched_task=None, lang: str = "ru", ) -> str:
    system_prompt = (
        "Ты ассистент, который помогает с действиями на экране. "
        "Сначала напиши строку вида: intent: allowed или intent: rejected. "
        "- allowed: если запрос связан с действием или выбором на экране "
        "- rejected: если запрос теоретический или выходит за рамки экранной помощи. "
        "Затем выяви конкретный шаг, о котором идет речь. Объясни только этот шаг максимально подробно. Если не удается выявить шаг, в качестве ответа задай уточняющий вопрос"
        "Если intent: rejected - скажи: 'Я помогаю только с действиями на экране. Спроси, что сделать.'"
    )

    if matched_task:
        system_prompt += (
            f"\nРядом подходящая инструкция: {matched_task['title']}.\n"
            f"Описание:\n{matched_task['intro'].strip()[:800]}"
        )

    # Inject session history
    history = SESSION_STORE.get(session_id, {}).get("history", [])[-MEMORY_LIMIT:]
    history_text = "\n".join(
        f"Пользователь: {h['text']}\nАссистент: {h['reply']}" for h in history
    )

    messages = [
        {"role": "system", "content": system_prompt},
    ]

    if history_text:
        messages.append({"role": "system", "content": f"История взаимодействия:\n{history_text}"})

    messages.append({"role": "user", "content": text})

    try:
        chat = openai_client.chat.completions.create(
            model="gpt-4o" if vision_parts else "gpt-4",
            messages=messages
        )
        logger.log_time("🧠 GPT")

        full_reply = chat.choices[0].message.content.strip()

        if full_reply.lower().startswith("intent: rejected"):
            logger.info("⛔ Rejected prompt: %s", text[:100])
            trimmed = full_reply.split("\n", 1)[1].strip() if "\n" in full_reply else "Я не могу ответить на это."
            SESSION_STORE[session_id]["history"].append({"text": text, "reply": trimmed})
            SESSION_STORE[session_id]["history"] = SESSION_STORE[session_id]["history"][-MEMORY_LIMIT:]
            return generate_speech(openai_client, trimmed)

        if full_reply.lower().startswith("intent: allowed"):
            reply = full_reply.split("\n", 1)[1].strip() if "\n" in full_reply else "Окей, продолжим."
        else:
            logger.info("⚠️ Missing intent tag in GPT reply.")
            reply = full_reply

        if not reply or len(reply) < 20:
            reply = "Извините, я не смог определить следующий шаг."

        SESSION_STORE[session_id]["history"].append({"text": text, "reply": reply})
        SESSION_STORE[session_id]["history"] = SESSION_STORE[session_id]["history"][-MEMORY_LIMIT:]

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(generate_speech, openai_client, reply)
            mp3_data = future.result()
            logger.log_time("🔊 TTS")

        return mp3_data

    except Exception as e:
        logger.error("❌ GPT or TTS error:", e)
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9091, debug=True)
