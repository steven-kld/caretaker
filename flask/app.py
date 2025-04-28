from flask import Flask, request, jsonify, Response, session
from flask_cors import CORS
import os, uuid, openai
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv

from utils.logging import LogManager
from core.faiss_matcher import FaissMatcher, MatchStatus
from core.session_manager import SessionManager
from core.process_manager import ProcessManager

APP_FOLDER = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

log_manager = LogManager()

faiss_matcher = FaissMatcher(
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

        query, error = ProcessManager.transcribe_audio(openai_client, logger)
        if not query:
            return jsonify({'error': error}), 400
        
        logger.info(f"Received user input: {query}")

        # --- Matching and task handling ---
        match_result = faiss_matcher.process(session_id, query, openai_client, logger)

        # --- Generate final response ---
        mp3_data = generate_response(
            openai_client,
            query,
            session_id,
            logger,
            match_result
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
    

def generate_response(openai_client, query, session_id, logger, match_result):
    try:
        history = SessionManager.get_history(session_id)

        system_prompt = (
            "Ты помогаешь выполнять действия на экране. "
            "Отвечай очень коротко и просто — 1–2 предложения. "
            "Никаких лишних объяснений, никаких сложных фраз."
        )

        messages = [{"role": "system", "content": system_prompt}]

        if history:
            history_text = "\n".join(
                f"Пользователь: {h['text']}\nАссистент: {h['reply']}" for h in history
            )
            messages.append({"role": "system", "content": f"История общения:\n{history_text}"})

        # --- Three paths based on match result ---
        if match_result.status == MatchStatus.MATCHED and match_result.step:
            # ✅ Matched step: use step full text
            user_content = (
                f"Текущий шаг:\n{match_result.step.get('text', '')}\n\n"
                f"Вопрос пользователя:\n{query}"
            )
            messages.append({"role": "user", "content": user_content})

        elif match_result.status == MatchStatus.NO_STEP_MATCH and match_result.task:
            # ✅ Matched task but no step: list steps
            steps = match_result.task.get('steps', [])
            steps_list = "\n".join(
                f"- {step.get('text', '').strip()}" for step in steps
            )
            user_content = (
                f"Есть такие шаги:\n{steps_list}\n\n"
                f"Пользователь спросил:\n{query}\n\n"
                "Помоги выбрать шаг. Ответь коротко, без лишних слов."
            )
            messages.append({"role": "user", "content": user_content})

        elif match_result.status == MatchStatus.NO_TASK_MATCH:
            # ❌ No task matched
            reply = "Я не понял, что нужно сделать. Попробуйте переформулировать запрос."
            SessionManager.save_history(session_id, query, reply)
            return generate_speech(openai_client, reply)

        # --- Call GPT ---
        logger.info("RESPONSE PROMPT")
        logger.info(messages)

        chat = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        logger.log_time("🧠 GPT")

        full_reply = chat.choices[0].message.content.strip()

        if not full_reply or len(full_reply) < 10:
            full_reply = "Извините, не смог точно определить действие."

        SessionManager.save_history(session_id, query, full_reply)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(generate_speech, openai_client, full_reply)
            mp3_data = future.result()
            logger.log_time("🔊 TTS")

        return mp3_data

    except Exception as e:
        logger.error("❌ GPT or TTS error:", e)
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9091, debug=True)
