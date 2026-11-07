"""Structured JSON logging shared by all fake-system services.

Every log line is one JSON object matching `LogEvent`. Core fields have fixed
names so Elasticsearch aggregations and the agent's `search_logs` tool can rely
on them; anything else goes in the free-form `extra` object.
"""

import logging
import os
import sys
import traceback
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

MAX_STACK_CHARS = 2000

# Attributes every LogRecord has. Anything else passed via `extra=` is ours.
_STANDARD_RECORD_ATTRS = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}

# Core fields a caller may pass via `extra=`; the rest land in LogEvent.extra.
_CORE_FIELDS = {"event", "request_id", "trace_id", "route", "status", "duration_ms"}


class ErrorInfo(BaseModel):
    type: str
    stack: str | None = None


class LogEvent(BaseModel):
    """One log line. Serialised with `by_alias=True, exclude_none=True`."""

    model_config = ConfigDict(populate_by_name=True)

    timestamp: datetime = Field(alias="@timestamp")
    service: str
    version: str  # git tag of the deployed build, e.g. "v1.1.0"
    commit: str  # git commit of the deployed build
    level: str
    event: str  # stable snake_case name, e.g. "charge_failed"
    message: str
    request_id: str | None = None
    trace_id: str | None = None
    route: str | None = None
    status: int | None = None
    duration_ms: float | None = None
    error: ErrorInfo | None = None
    extra: dict = Field(default_factory=dict)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, version: str, commit: str) -> None:
        super().__init__()
        self.service = service
        self.version = version
        self.commit = commit

    def format(self, record: logging.LogRecord) -> str:
        custom = {
            k: v for k, v in record.__dict__.items() if k not in _STANDARD_RECORD_ATTRS
        }
        core = {k: custom.pop(k) for k in list(custom) if k in _CORE_FIELDS}

        error = None
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc, tb = record.exc_info
            stack = "".join(traceback.format_exception(exc_type, exc, tb))
            error = ErrorInfo(type=exc_type.__name__, stack=stack[-MAX_STACK_CHARS:])

        event = LogEvent(
            timestamp=datetime.fromtimestamp(record.created, tz=UTC),
            service=self.service,
            version=self.version,
            commit=self.commit,
            level=record.levelname.lower(),
            event=core.pop("event", "log"),
            message=record.getMessage(),
            error=error,
            extra=custom,
            **core,
        )
        return event.model_dump_json(by_alias=True, exclude_none=True)


def get_logger(service: str) -> logging.Logger:
    """Logger that writes JSON lines to stdout.

    Version and commit come from the SHERLOG_VERSION / SHERLOG_COMMIT env vars,
    which the deploy step sets, so each line is traceable to a deploy.
    """
    logger = logging.getLogger(f"fake_system.{service}")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            service=service,
            version=os.environ.get("SHERLOG_VERSION", "unknown"),
            commit=os.environ.get("SHERLOG_COMMIT", "unknown"),
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
