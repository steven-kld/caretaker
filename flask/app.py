from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, openai, base64, logging, time
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    filename='latency.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = './temp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/api/session/init")
def init_session():
    return jsonify({"ok": "hello dear"})

@app.route('/api/process', methods=['POST'])
def process():
    try:
        start = time.time()

        openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        logging.info("📥 OpenAI init in %.3f sec", time.time() - start)
        start = time.time()

        audio = request.files.get('audio')
        logging.info("📥 Audio received in %.3f sec", time.time() - start)
        start = time.time()

        if not audio or not hasattr(audio.stream, 'read'):
            return jsonify({'error': 'No valid audio file'}), 400

        # 🧠 Read the binary content once
        raw_bytes = audio.read()
        if not raw_bytes:
            return jsonify({'error': 'Empty audio stream'}), 400

        # 💾 Wrap in BytesIO for OpenAI
        buffer = BytesIO(raw_bytes)
        buffer.name = audio.filename  # required by OpenAI SDK
        logging.info("📦 Audio wrapped in %.3f sec", time.time() - start)
        start = time.time()

        # 🧠 Transcribe with Whisper
        response = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=buffer,
            response_format="verbose_json"
        )
        logging.info("🧠 Whisper took %.3f sec", time.time() - start)
        start = time.time()

        if not response.text:
            return jsonify({'error': 'Missing text'}), 400

        # ✅ Parallel base64 encoding for image files
        image_files = request.files.getlist("images")
        logging.info("🖼 Image encoding took %.3f sec", time.time() - start)
        start = time.time()
        with ThreadPoolExecutor() as executor:
            encoded_images = list(executor.map(
                lambda img: base64.b64encode(img.read()).decode("utf-8"),
                image_files[:5]  # safety cap
            ))

        vision_parts = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            }
            for b64 in encoded_images
        ]

        mp3_data = generate_response(openai_client, response.text, vision_parts)
        logging.info("🤖 GPT + TTS took %.3f sec", time.time() - start)
        if not mp3_data:
            return jsonify({'error': 'TTS failed'}), 500

        return Response(mp3_data, mimetype="audio/mpeg")

    except Exception as e:
        print("❌ Whisper failed:", e)
        return jsonify({'error': str(e)}), 500


def generate_speech(openai_client, text, voice="nova"):
    try:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        return response.content  # MP3 binary

    except Exception as e:
        print("❌ TTS failed:", e)
        return None


def generate_response(openai_client, text, vision_parts, lang: str = "ru") -> str:
    system_prompt = (
        "Ты ассистент, который помогает с действиями на экране. "
        "Сначала напиши строку вида: intent: allowed или intent: rejected. "
        "- allowed: если запрос связан с действием или выбором на экране "
        "- rejected: если запрос теоретический или выходит за рамки экранной помощи. "
        "Затем дай короткий, уверенный ответ. Никогда не объясняй подробно. "
        "Если intent: rejected — скажи: 'Я помогаю только с действиями на экране. Спроси, что сделать.'"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]

    try:
        gpt_start = time.time()
        chat = openai_client.chat.completions.create(
            model="gpt-4o" if vision_parts else "gpt-4",
            messages=messages
        )
        logging.info("🧠 GPT took %.3f sec", time.time() - gpt_start)

        full_reply = chat.choices[0].message.content.strip()

        # Parse intent and actual message
        if full_reply.lower().startswith("intent: rejected"):
            logging.info("⛔ Rejected prompt: %s", text[:100])
            trimmed = full_reply.split("\n", 1)[1].strip() if "\n" in full_reply else "Я не могу ответить на это."
            return generate_speech(openai_client, trimmed)

        if full_reply.lower().startswith("intent: allowed"):
            reply = full_reply.split("\n", 1)[1].strip() if "\n" in full_reply else "Окей, продолжим."
        else:
            # Fallback if GPT forgot to tag
            logging.warning("⚠️ Missing intent tag in GPT reply.")
            reply = full_reply

        if not reply or len(reply) < 10:
            reply = "Извините, я не смог определить следующий шаг."

        # ✅ Run TTS in a separate thread
        tts_start = time.time()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(generate_speech, openai_client, reply)
            mp3_data = future.result()
            logging.info("🔊 TTS took %.3f sec", time.time() - tts_start)

        return mp3_data

    except Exception as e:
        print("❌ GPT or TTS error:", e)
        return None



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9091, debug=True)
