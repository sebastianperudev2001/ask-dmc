"""Structured JSON logging (SECURITY-03) — shipped to Azure Monitor / Log Analytics via
the Container Apps log driver (stdout). No PII: request bodies are never logged verbatim,
only lengths/ids where needed for debugging.

DIV-16 exception (scoped): the chat entry message, agent reasoning, and tool-call logs in
`api/chat_websocket_handler.py` / `adapters/chat_agent_client.py` log full text verbatim by
explicit user decision for this demo project — not a general repeal of the no-PII rule
above, which still applies everywhere else.

Locally (AGENT_SERVICE_ENV=local, the default), logs are colorized for readability instead
of JSON — colorlog is a dev-only dependency (see pyproject.toml [project.optional-dependencies]
dev) and is never installed in the production image (Dockerfile runs `pip install .`), so
production always gets JSONFormatter regardless of import availability.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

_STANDARD_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


def _extra_fields(record: logging.LogRecord) -> dict:
    """Fields passed via `logger.info(..., extra={...})` — anything on the record that
    isn't one of Python logging's own standard attributes."""
    return {key: value for key, value in record.__dict__.items() if key not in _STANDARD_LOG_RECORD_ATTRS}


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _build_formatter() -> logging.Formatter:
    env = os.environ.get("AGENT_SERVICE_ENV", "local").strip().lower()
    if env != "local":
        return JSONFormatter()

    try:
        from colorlog import ColoredFormatter
    except ImportError:
        return JSONFormatter()

    class _LocalFormatter(ColoredFormatter):
        """`ColoredFormatter`'s format string only renders `%(message)s` — `extra=`
        fields (e.g. conversation_id, user_message, reasoning) were silently invisible
        locally even though JSONFormatter already emitted them in production. Appends
        them to the message before delegating so local stdout shows the same data."""

        def format(self, record: logging.LogRecord) -> str:
            extras = _extra_fields(record)
            if extras:
                suffix = " ".join(f"{key}={value!r}" for key, value in extras.items())
                record.msg = f"{record.getMessage()} | {suffix}"
                record.args = ()
            return super().format(record)

    return _LocalFormatter(
        "%(log_color)s%(asctime)s %(levelname)-8s%(reset)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("agent_service")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_build_formatter())
    logger.addHandler(handler)
    return logger
