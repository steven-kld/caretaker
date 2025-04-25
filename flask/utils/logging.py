import logging
import sys
import time
from pathlib import Path

class SessionLogger:
    def __init__(self, session_id: str, base_logger: logging.Logger):
        self.session_id = session_id
        self.logger = base_logger
        self.timer = None

    def info(self, msg, *args):
        self.logger.info(f"[{self.session_id}] {msg}", *args)

    def error(self, msg, *args):
        self.logger.error(f"[{self.session_id}] {msg}", *args)

    def exception(self, msg, *args):
        self.logger.exception(f"[{self.session_id}] {msg}", *args)

    def start_timer(self):
        self.timer = time.time()

    def log_time(self, label: str):
        if self.timer is None:
            self.info(f"⏱️ Timer not started for: {label}")
        else:
            duration = time.time() - self.timer
            self.info(f"{label} in {duration:.3f} sec")
            self.timer = time.time()  # auto-reset


class LogManager:
    def __init__(self, log_file: str = "main.log"):
        log_path = Path(__file__).parent.parent / log_file
        log_path.open("w").close()  # Clear on start

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("Needlee")
        self.logger.info("✅ LogManager initialized")

    def get_session_logger(self, session_id: str) -> SessionLogger:
        return SessionLogger(session_id, self.logger)
