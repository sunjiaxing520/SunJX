import json
import logging
import re
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.core.config import settings


LOGGER_NAME = "blue_music"
CONTEXT_FIELDS = (
    "request_id",
    "task_id",
    "user_id",
    "method",
    "path",
    "status_code",
    "error_code",
    "agent",
    "step",
    "attempt",
)
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)((?:password(?:_hash)?|token|authorization|cookie|secret(?:_key)?|"
    r"api[_-]?key)[\"']?\s*[:=]\s*[\"']?)([^\s,\"';]+)"
)
URL_PASSWORD_PATTERN = re.compile(r"(\w+://[^:/\s]+:)[^@\s]+@")


def redact_sensitive_values(value: str) -> str:
    value = SENSITIVE_VALUE_PATTERN.sub(r"\1***", value)
    return URL_PASSWORD_PATTERN.sub(r"\1***@", value)


def _context_from_record(record: logging.LogRecord) -> dict[str, object]:
    return {
        field: value
        for field in CONTEXT_FIELDS
        if (value := getattr(record, field, None)) is not None
    }


class TextLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()
        context = " ".join(
            f"{key}={value}" for key, value in _context_from_record(record).items()
        )
        event = redact_sensitive_values(record.getMessage())
        line = f"{timestamp} {record.levelname} {record.name} {event}"
        if context:
            line = f"{line} {context}"
        if record.exc_info:
            exception = redact_sensitive_values(self.formatException(record.exc_info))
            line = f"{line}\n{exception}"
        return line


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        content: dict[str, object] = {
            "time": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": redact_sensitive_values(record.getMessage()),
            "service": settings.SERVICE_NAME,
            "environment": settings.ENVIRONMENT,
            **_context_from_record(record),
        }
        if record.exc_info:
            content["exception"] = redact_sensitive_values(
                self.formatException(record.exc_info)
            )
        return json.dumps(content, ensure_ascii=False)


def get_log_directory() -> Path:
    if settings.LOG_DIR:
        return Path(settings.LOG_DIR).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "logs"


def get_log_file() -> Path:
    return get_log_directory() / "app.log"


def _formatter() -> logging.Formatter:
    if settings.LOG_FORMAT == "json":
        return JsonLogFormatter()
    return TextLogFormatter()


def configure_logging() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return

    formatter = _formatter()
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.setLevel(settings.LOG_LEVEL)
    logger.addHandler(stream_handler)
    logger.propagate = False

    if settings.LOG_TO_FILE:
        log_directory = get_log_directory()
        log_directory.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            get_log_file(),
            when="midnight",
            backupCount=settings.LOG_RETENTION_DAYS,
            encoding="utf-8",
            utc=True,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
