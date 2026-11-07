import io
import json
import logging

import pytest

from fake_system.common.logs import JsonFormatter, LogEvent


@pytest.fixture
def log_stream():
    return io.StringIO()


@pytest.fixture
def logger(log_stream):
    """A logger that writes schema-formatted JSON lines into `log_stream`."""
    lg = logging.getLogger("test.service")
    lg.handlers.clear()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JsonFormatter("test", "v1.0.0", "abc123"))
    lg.addHandler(handler)
    lg.setLevel(logging.INFO)
    lg.propagate = False
    return lg


@pytest.fixture
def read_events(log_stream):
    """Every logged line, validated against the LogEvent schema."""
    def _read() -> list[LogEvent]:
        return [LogEvent.model_validate(json.loads(line))
                for line in log_stream.getvalue().splitlines()]
    return _read
