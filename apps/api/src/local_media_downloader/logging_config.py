"""Structured JSON logging.

Every log line is a single JSON object so it stays parseable without a
central log server. Shape:

    {"timestamp": ..., "level": ..., "component": ..., "event": ...}

Never log tokens, cookies, authorization headers or raw URLs beyond what the
user explicitly configured to redact.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "component": getattr(record, "component", record.name),
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_") and key not in payload:
                try:
                    json.dumps(value)
                    payload[key] = value
                except TypeError:
                    payload[key] = str(value)
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(component: str) -> logging.LoggerAdapter:
    logger = logging.getLogger(component)
    return logging.LoggerAdapter(logger, {"component": component})
