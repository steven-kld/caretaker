from flask import Flask, request, jsonify, Response, session
from flask_cors import CORS
import os, uuid, openai
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv

from utils.logging import LogManager
from core.faiss_matcher import FaissMatcher, MatchAction
from core.session_manager import SessionManager
from core.process_manager import ProcessManager

APP_FOLDER = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

log_manager = LogManager()

task_matcher = FaissMatcher(
    index_path=Path("./model/vector/task_index.faiss"),
    meta_path=Path("./model/vector/task_meta.json")
)

@app.route("/api/session/init", methods=['GET'])
def init_session():
    SessionManager.clear_expired_sessions()

    if not session.get('user_id'):
        session['user_id'] = str(uuid.uuid4())
    user_id = session['user_id']

    logger = log_manager.get_session_logger(user_id)
    SessionManager.init_session(user_id, logger)

    logger.info(f"🆕 Session initialized and logger attached for uuid {user_id}")
    return jsonify({"ok": "hello dear", "session_id": user_id})

@app.route('/api/process', methods=['POST'])
def process():
    try:
        # --- Always needed preparations ---
        session_id, logger = ProcessManager.prepare_session(session)
        if not session_id:
            return jsonify({'error': logger}), 400

        openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        text, error = ProcessManager.transcribe_audio(openai_client, logger)
        if not text:
            return jsonify({'error': error}), 400
        
        logger.info(f"Received user input: {text}")

        vision_parts = ProcessManager.prepare_vision_parts(logger)

        # --- Matching and task handling ---
        match_result = task_matcher.match_task_or_continue(session_id, text, openai_client, logger)

        if match_result.action == MatchAction.LOCKED_NEW_TASK:
            logger.log_time(f"📌 New task locked: {match_result.task['title']}")

        elif match_result.action == MatchAction.CONTINUING_TASK:
            logger.log_time(f"➡️ Continuing task at step {match_result.step}")

        elif match_result.action == MatchAction.MISMATCH_UNLOCK:
            logger.log_time("⛔ Mismatch detected, unlocked")

        elif match_result.action == MatchAction.TASK_COMPLETED_UNLOCK:
            logger.log_time("✅ Task completed, unlocked")

        elif match_result.action == MatchAction.NO_MATCH_FOUND:
            logger.log_time("⚠️ No matching task found")

        # --- Generate final response ---
        mp3_data = generate_response(
            openai_client,
            text,
            vision_parts,
            session_id,
            logger,
            matched_task=match_result.task,
            matched_step=match_result.step_info if hasattr(match_result, "step_info") else None
        )

        logger.log_time("🤖 GPT + TTS")

        if not mp3_data:
            return jsonify({'error': 'TTS failed'}), 500

        return Response(mp3_data, mimetype="audio/mpeg")

    except Exception as e:
        logger.error("❌ process failed:", e)
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

def generate_response(openai_client, text, vision_parts, session_id, logger, matched_task=None, matched_step=None, lang: str = "ru"):
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

    if matched_step:
        system_prompt += (
            f"\n\nТекущий конкретный шаг:\n{matched_step.get('text', '')}"
        )


    history = SessionManager.get_history(session_id)
    history_text = "\n".join(
        f"Пользователь: {h['text']}\nАссистент: {h['reply']}" for h in history
    )

    messages = [{"role": "system", "content": system_prompt}]
    if history_text:
        messages.append({"role": "system", "content": f"История взаимодействия:\n{history_text}"})
    messages.append({"role": "user", "content": text})

    logger.info("RESPONSE PROMPT")
    logger.info(messages)
    
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
            SessionManager.save_history(session_id, text, trimmed)
            return generate_speech(openai_client, trimmed)

        if full_reply.lower().startswith("intent: allowed"):
            reply = full_reply.split("\n", 1)[1].strip() if "\n" in full_reply else "Окей, продолжим."
        else:
            logger.info("⚠️ Missing intent tag in GPT reply.")
            reply = full_reply

        if not reply or len(reply) < 20:
            reply = "Извините, я не смог определить следующий шаг."

        SessionManager.save_history(session_id, text, reply)

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
