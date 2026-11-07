import httpx
import pytest
from fastapi.testclient import TestClient

from fake_system.checkout.app.main import create_app

ORDER = {"order_id": "o1", "sku": "sku-a", "quantity": 1, "amount_cents": 500}


class Downstream:
    """Scripted inventory + payments behind httpx.MockTransport."""

    def __init__(self, inventory_status=200, payments_status=200,
                 payments_raises: Exception | None = None) -> None:
        self.inventory_status = inventory_status
        self.payments_status = payments_status
        self.payments_raises = payments_raises
        self.calls: list[httpx.Request] = []

    def inventory(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(self.inventory_status, json={"sku": "sku-a", "reserved": 1})

    def payments(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.payments_raises:
            raise self.payments_raises
        return httpx.Response(self.payments_status,
                              json={"charge_id": "c1", "status": "succeeded"})

    def client(self, logger):
        inv = httpx.Client(base_url="http://inventory",
                           transport=httpx.MockTransport(self.inventory))
        pay = httpx.Client(base_url="http://payments",
                           transport=httpx.MockTransport(self.payments))
        return TestClient(create_app(inventory=inv, payments=pay, logger=logger))


def test_success_calls_both_services_and_propagates_request_id(logger):
    ds = Downstream()
    with ds.client(logger) as client:
        resp = client.post("/checkout", json=ORDER, headers={"x-request-id": "req-1"})
    assert resp.status_code == 200
    assert resp.json() == {"order_id": "o1", "charge_id": "c1", "status": "completed"}
    assert [r.url.host for r in ds.calls] == ["inventory", "payments"]
    assert all(r.headers["x-request-id"] == "req-1" for r in ds.calls)


def test_out_of_stock_does_not_charge(logger):
    ds = Downstream(inventory_status=409)
    with ds.client(logger) as client:
        resp = client.post("/checkout", json=ORDER)
    assert resp.status_code == 409
    assert [r.url.host for r in ds.calls] == ["inventory"]


def test_payment_error_returns_502_and_logs(logger, read_events):
    with Downstream(payments_status=500).client(logger) as client:
        resp = client.post("/checkout", json=ORDER)
    assert resp.status_code == 502
    events = {e.event: e for e in read_events()}
    assert events["checkout_failed"].level == "error"
    assert events["checkout_failed"].extra["payments_status"] == 500


def test_payments_timeout_returns_502_and_logs_dependency(logger, read_events):
    ds = Downstream(payments_raises=httpx.ReadTimeout("slow"))
    with ds.client(logger) as client:
        resp = client.post("/checkout", json=ORDER)
    assert resp.status_code == 502
    failed = [e for e in read_events() if e.event == "downstream_failed"]
    assert len(failed) == 1
    assert failed[0].extra["dependency"] == "payments"
    assert failed[0].error.type == "ReadTimeout"
    assert failed[0].duration_ms is not None


def test_invalid_order_rejected(logger):
    with Downstream().client(logger) as client:
        assert client.post("/checkout", json={**ORDER, "quantity": 0}).status_code == 422
