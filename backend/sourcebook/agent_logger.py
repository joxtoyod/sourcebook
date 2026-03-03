import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


class AgentLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._websocket = None
        self._file_logger = None  # initialized lazily on first log call

    def _ensure_logger(self):
        if self._file_logger:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("sourcebook.agent")
        logger.setLevel(logging.DEBUG)
        # Avoid adding duplicate handlers on re-import
        if not logger.handlers:
            handler = RotatingFileHandler(
                self.log_path, maxBytes=500_000, backupCount=2, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(message)s"))  # raw JSONL
            logger.addHandler(handler)
        self._file_logger = logger

    def attach(self, ws):
        self._websocket = ws

    def detach(self):
        self._websocket = None

    async def log(self, level: str, msg: str):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": level,
            "msg": msg,
        }
        try:
            self._ensure_logger()
            self._file_logger.info(json.dumps(entry))
        except Exception:
            pass
        if self._websocket:
            try:
                await self._websocket.send_json({"type": "agent_log", "entry": entry})
            except Exception:
                pass

    async def info(self, msg: str):
        await self.log("info", msg)

    async def error(self, msg: str):
        await self.log("error", msg)

    def read_tail(self, n: int = 200) -> list:
        """Read last n log entries from current log file."""
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
            return [json.loads(l) for l in lines[-n:] if l.strip()]
        except Exception:
            return []


from sourcebook.config import settings

agent_logger = AgentLogger(settings.log_path)
