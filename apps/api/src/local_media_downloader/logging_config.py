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

# Secrets registered at runtime (currently the API token). Redaction happens on
# the formatted message and on every extra field, so a token can never reach
# stderr even if it is passed through ``extra`` by mistake.
_SECRETS: set[str] = set()
_REDACTED = "***redacted***"


def register_secret(value: str | None) -> None:
    """Mark a value as a secret so the formatter masks it everywhere."""
    if value and len(value) >= 8:
        _SECRETS.add(value)


def redact(text: str) -> str:
    for secret in _SECRETS:
        if secret in text:
            text = text.replace(secret, _REDACTED)
    return text


def _scrub(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    return value


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "component": getattr(record, "component", record.name),
            "event": redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_") and key not in payload:
                try:
                    json.dumps(value)
                    payload[key] = _scrub(value)
                except TypeError:
                    payload[key] = _scrub(str(value))
        if record.exc_info:
            payload["error"] = redact(self.formatException(record.exc_info))
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
