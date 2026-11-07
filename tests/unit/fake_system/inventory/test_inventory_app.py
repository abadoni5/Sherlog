import pytest
from fastapi.testclient import TestClient

from fake_system.inventory.app.main import create_app


class FakeStore:
    def __init__(self) -> None:
        self.stock = {"sku-a": 3}

    def get_stock(self, sku):
        return self.stock.get(sku)

    def reserve(self, sku, quantity):
        if self.stock.get(sku, 0) < quantity:
            return False
        self.stock[sku] -= quantity
        return True

    def close(self) -> None:
        pass


@pytest.fixture
def client(logger):
    with TestClient(create_app(store=FakeStore(), logger=logger)) as c:
        yield c


def test_stock_lookup(client):
    assert client.get("/stock/sku-a").json() == {"sku": "sku-a", "quantity": 3}
    assert client.get("/stock/nope").status_code == 404


def test_reserve_decrements_stock(client):
    resp = client.post("/reserve", json={"sku": "sku-a", "quantity": 2})
    assert resp.status_code == 200
    assert client.get("/stock/sku-a").json()["quantity"] == 1


def test_reserve_insufficient_or_unknown_is_409_and_logged(client, read_events):
    assert client.post("/reserve", json={"sku": "sku-a", "quantity": 9}).status_code == 409
    assert client.post("/reserve", json={"sku": "nope", "quantity": 1}).status_code == 409
    rejected = [e for e in read_events() if e.event == "reserve_rejected"]
    assert len(rejected) == 2 and rejected[0].level == "warning"


def test_reserve_validates_quantity(client):
    assert client.post("/reserve", json={"sku": "sku-a", "quantity": 0}).status_code == 422
