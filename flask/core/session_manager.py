import time

SESSION_STORE = {}

class SessionManager:
    MEMORY_LIMIT = 10
    SESSION_LIFETIME_SECONDS = 3600  # 1 hour

    @staticmethod
    def init_session(session_id, logger):
        SESSION_STORE[session_id] = {
            "history": [],
            "logger": logger,
            "matched_task": None,
            "current_step": 0,             # Added current_step
            "created_at": time.time(),
            "updated_at": time.time()
        }

    @staticmethod
    def get_logger(session_id):
        SessionManager._refresh(session_id)
        return SESSION_STORE.get(session_id, {}).get("logger")

    @staticmethod
    def get_history(session_id):
        SessionManager._refresh(session_id)
        return SESSION_STORE.get(session_id, {}).get("history", [])

    @staticmethod
    def save_history(session_id, user_text, assistant_reply):
        if session_id not in SESSION_STORE:
            return
        SESSION_STORE[session_id]["history"].append({
            "text": user_text,
            "reply": assistant_reply
        })
        SESSION_STORE[session_id]["history"] = SESSION_STORE[session_id]["history"][-SessionManager.MEMORY_LIMIT:]
        SessionManager._refresh(session_id)

    @staticmethod
    def set_matched_task(session_id, task_match):
        if session_id in SESSION_STORE:
            SESSION_STORE[session_id]["matched_task"] = task_match
            SessionManager._refresh(session_id)

    @staticmethod
    def get_matched_task(session_id):
        SessionManager._refresh(session_id)
        return SESSION_STORE.get(session_id, {}).get("matched_task")

    @staticmethod
    def set_current_step(session_id, step_num):
        if session_id in SESSION_STORE:
            SESSION_STORE[session_id]["current_step"] = step_num
            SessionManager._refresh(session_id)

    @staticmethod
    def get_current_step(session_id):
        return SESSION_STORE.get(session_id, {}).get("current_step", 0)

    @staticmethod
    def unlock_task(session_id):
        if session_id in SESSION_STORE:
            SESSION_STORE[session_id]["matched_task"] = None
            SESSION_STORE[session_id]["current_step"] = 0
            SessionManager._refresh(session_id)

    @staticmethod
    def session_exists(session_id):
        SessionManager._refresh(session_id)
        return session_id in SESSION_STORE

    @staticmethod
    def clear_session(session_id):
        if session_id in SESSION_STORE:
            del SESSION_STORE[session_id]

    @staticmethod
    def clear_expired_sessions():
        now = time.time()
        expired = [
            sid for sid, data in SESSION_STORE.items()
            if now - data.get("updated_at", 0) > SessionManager.SESSION_LIFETIME_SECONDS
        ]
        for sid in expired:
            del SESSION_STORE[sid]

    @staticmethod
    def _refresh(session_id):
        """Private helper to update session activity time."""
        if session_id in SESSION_STORE:
            SESSION_STORE[session_id]["updated_at"] = time.time()
