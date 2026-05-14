import json
import logging
import logging.config
from datetime import datetime, timezone

_SKIP_ATTRS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "taskName", "thread", "threadName",
})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        log: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.message,
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key not in _SKIP_ATTRS and not key.startswith("_"):
                log[key] = val
        return json.dumps(log, default=str)


def setup_logging(debug: bool = False) -> None:
    level = "DEBUG" if debug else "INFO"
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": JsonFormatter},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json",
            },
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            # Take over uvicorn's loggers so they emit JSON instead of plain text.
            # propagate=False prevents double-logging once we replace their handlers.
            "uvicorn": {"handlers": ["console"], "propagate": False, "level": "INFO"},
            "uvicorn.error": {"handlers": ["console"], "propagate": False, "level": "INFO"},
            "uvicorn.access": {"handlers": ["console"], "propagate": False, "level": "INFO"},
        },
    })
