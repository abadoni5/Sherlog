import json
import logging

from fake_system.common.logs import MAX_STACK_CHARS, JsonFormatter, LogEvent


def _format(record_kwargs: dict, exc: BaseException | None = None) -> dict:
    formatter = JsonFormatter(service="payments", version="v1.0.0", commit="abc123")
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, record_kwargs.pop("msg", "hello"), (), None
    )
    for key, value in record_kwargs.items():
        setattr(record, key, value)
    if exc is not None:
        record.exc_info = (type(exc), exc, exc.__traceback__)
    return json.loads(formatter.format(record))


def test_line_validates_against_schema():
    line = _format({"event": "charge_ok", "route": "/charge", "status": 200,
                    "duration_ms": 12.5, "request_id": "r1"})
    event = LogEvent.model_validate(line)
    assert event.service == "payments"
    assert event.version == "v1.0.0"
    assert event.level == "info"
    assert event.status == 200


def test_timestamp_uses_elasticsearch_field_name_and_is_utc():
    line = _format({})
    assert "@timestamp" in line and "timestamp" not in line
    assert line["@timestamp"].endswith("Z") or line["@timestamp"].endswith("+00:00")


def test_missing_optional_fields_are_omitted_and_event_defaults():
    line = _format({})
    assert line["event"] == "log"
    for absent in ("request_id", "route", "status", "error"):
        assert absent not in line


def test_unknown_fields_go_to_extra():
    line = _format({"event": "x", "order_id": 42})
    assert line["extra"] == {"order_id": 42}


def test_exception_is_captured_and_stack_truncated():
    try:
        raise ValueError("boom " * 1000)
    except ValueError as exc:
        line = _format({"event": "charge_failed", "msg": "failed"}, exc=exc)
    assert line["error"]["type"] == "ValueError"
    assert len(line["error"]["stack"]) <= MAX_STACK_CHARS
    LogEvent.model_validate(line)
