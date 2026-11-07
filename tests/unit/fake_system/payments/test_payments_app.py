import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

from fake_system.common.logs import JsonFormatter, LogEvent
from fake_system.payments.app.main import create_app


class FakeStore:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.rows: list[tuple] = []

    def insert_charge(self, order_id, amount_cents, currency):
        if self.fail:
            raise ConnectionError("db down")
        self.rows.append((order_id, amount_cents, currency))
        return f"charge-{len(self.rows)}"

    def close(self) -> None:
        pass


@pytest.fixture
def log_stream():
    return io.StringIO()


@pytest.fixture
def make_client(log_stream):
    logger = logging.getLogger("test.payments")
    logger.handlers.clear()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JsonFormatter("payments", "v1.0.0", "abc123"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    def _make(store):
        # `with TestClient(...)` runs the lifespan (startup/shutdown).
        return TestClient(create_app(store=store, logger=logger))

    return _make


def _events(log_stream) -> list[LogEvent]:
    return [LogEvent.model_validate(json.loads(line))
            for line in log_stream.getvalue().splitlines()]


def test_health(make_client):
    with make_client(FakeStore()) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_charge_success_persists_and_logs(make_client, log_stream):
    store = FakeStore()
    with make_client(store) as client:
        resp = client.post("/charge", json={"order_id": "o1", "amount_cents": 500})
    assert resp.status_code == 200
    assert resp.json() == {"charge_id": "charge-1", "status": "succeeded"}
    assert store.rows == [("o1", 500, "USD")]
    names = [e.event for e in _events(log_stream)]
    assert "charge_succeeded" in names and "request_completed" in names


@pytest.mark.parametrize("body", [
    {"order_id": "o1", "amount_cents": 0},
    {"order_id": "o1", "amount_cents": -5},
    {"order_id": "", "amount_cents": 100},
    {"order_id": "o1", "amount_cents": 100, "currency": "usd"},
])
def test_invalid_charge_rejected(make_client, body):
    with make_client(FakeStore()) as client:
        assert client.post("/charge", json=body).status_code == 422


def test_store_failure_returns_500_and_logs_error(make_client, log_stream):
    with make_client(FakeStore(fail=True)) as client:
        resp = client.post("/charge", json={"order_id": "o1", "amount_cents": 100})
    assert resp.status_code == 500
    failed = [e for e in _events(log_stream) if e.event == "charge_failed"]
    assert len(failed) == 1
    assert failed[0].level == "error"
    assert failed[0].error.type == "ConnectionError"


def test_request_id_is_echoed_and_logged(make_client, log_stream):
    with make_client(FakeStore()) as client:
        resp = client.get("/health", headers={"x-request-id": "req-42"})
    assert resp.headers["x-request-id"] == "req-42"
    assert _events(log_stream)[0].request_id == "req-42"
