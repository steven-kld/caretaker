from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, openai, base64
from io import BytesIO

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = './temp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/api/session/init")
def init_session():
    return jsonify({"ok": os.getenv("OPENAI_API_KEY")})

@app.route('/api/process', methods=['POST'])
def process():
    try:
        audio = request.files.get('audio')
        if not audio or not hasattr(audio.stream, 'read'):
            return jsonify({'error': 'No valid audio file'}), 400

        # 🧠 Read the binary content once
        raw_bytes = audio.read()
        if not raw_bytes:
            return jsonify({'error': 'Empty audio stream'}), 400

        # 💾 Wrap in BytesIO for OpenAI
        buffer = BytesIO(raw_bytes)
        buffer.name = audio.filename  # required by OpenAI SDK

        # 🔑 Create client per request
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # 🧠 Transcribe with Whisper
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=buffer,
            response_format="verbose_json"
        )
        if not response.text:
            return jsonify({'error': 'Missing text'}), 400

        # NEW THINGS HERE
        image_files = request.files.getlist("images")
        vision_parts = []
        for img in image_files[:5]:  # safety cap: max 1 image
            b64 = base64.b64encode(img.read()).decode("utf-8")
            vision_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
        
        mp3_data = generate_response(response.text, vision_parts)
        if not mp3_data:
            return jsonify({'error': 'TTS failed'}), 500

        return Response(mp3_data, mimetype="audio/mpeg")

    except Exception as e:
        print("❌ Whisper failed:", e)
        return jsonify({'error': str(e)}), 500

def generate_speech(client, text, voice="nova"):
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        return response.content  # MP3 binary

    except Exception as e:
        print("❌ TTS failed:", e)
        return None
    
def generate_response(text, vision_parts, lang: str = "ru") -> str:
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # 📦 Abstract, context-aware prompt
    prompt = [
        {"type": "text", "text": "На основе экрана и речи пользователя определи его намерение и подскажи, что делать дальше."}
    ] + vision_parts + [
        {"type": "text", "text": f"Голосовой ввод: {text}"}
    ]

    try:
        chat = client.chat.completions.create(
            model="gpt-4o" if vision_parts else "gpt-4",
            messages=[
                {"role": "system", "content": "Ты краткий, уверенный ассистент. Используй экран и голос, чтобы угадать, что хочет пользователь, и предложи следующий шаг. Не объясняй, просто подскажи."},
                {"role": "user", "content": prompt if vision_parts else text}
            ]
        )

        reply = chat.choices[0].message.content.strip()
        if not reply or len(reply) < 10:
            reply = "Извините, я не смог определить следующий шаг."

        return generate_speech(client, reply)

    except Exception as e:
        print("❌ GPT error:", e)
        return None

    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9091, debug=True)