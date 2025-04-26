# services/process_manager.py

import os, base64, time
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from flask import request
import openai
from core.session_manager import SessionManager

class ProcessManager:
    @staticmethod
    def prepare_session(session):
        SessionManager.clear_expired_sessions()
        
        session_id = session.get('user_id')
        if not session_id:
            return None, None, "Missing session_id"
        
        if not SessionManager.session_exists(session_id):
            return None, None, "Invalid session_id"
        
        logger = SessionManager.get_logger(session_id)
        logger.start_timer()
        
        return session_id, logger

    @staticmethod
    def transcribe_audio(openai_client, logger):
        audio = request.files.get('audio')
        logger.log_time("📥 Audio received")

        if not audio or not hasattr(audio.stream, 'read'):
            return None, "No valid audio file"

        raw_bytes = audio.read()
        if not raw_bytes:
            return None, "Empty audio stream"

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
            return None, "Missing text"

        return response.text, None

    @staticmethod
    def prepare_vision_parts(logger):
        image_files = request.files.getlist("images")

        if not image_files:
            logger.log_time("📷 No images uploaded")
            return []

        encoded_images = []

        def encode_safe(img):
            try:
                content = img.read()
                if not content:
                    return None
                return base64.b64encode(content).decode("utf-8")
            except Exception as e:
                logger.info(f"⚠️ Image read error: {str(e)}")
                return None

        with ThreadPoolExecutor() as executor:
            results = list(executor.map(encode_safe, image_files[:5]))

        for b64 in results:
            if b64:
                encoded_images.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

        logger.log_time("🖼 Image encoding complete")

        return encoded_images
