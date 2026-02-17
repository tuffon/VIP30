from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from datetime import datetime, timezone

from pythonjsonlogger import jsonlogger

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):  # type: ignore[no-untyped-def]
        super().add_fields(log_record, record, message_dict)
        log_record["request_id"] = request_id_ctx.get()
        log_record["timestamp"] = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name


def configure_logging() -> str:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(CustomJsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = []
    uvicorn_access.disabled = True

    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers = [handler]
    uvicorn_error.setLevel(level)
    uvicorn_error.propagate = False

    return log_level


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
