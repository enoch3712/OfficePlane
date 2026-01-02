import json
import logging
import os
import sys
import time
from contextvars import ContextVar
from typing import Any, Dict, Optional

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # allow extra fields via record.__dict__
        for k in ("stage", "port", "duration_ms", "filename", "pages"):
            if k in record.__dict__:
                payload[k] = record.__dict__[k]
        return json.dumps(payload, ensure_ascii=False)

def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = os.getenv("LOG_FORMAT", "json").lower()

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))

    # clear default handlers
    root.handlers = []
    root.addHandler(handler)
