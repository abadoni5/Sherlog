"""Needs a real Postgres. Set INVENTORY_TEST_DSN (see test_payments_store.py)."""
import os

import pytest

from fake_system.inventory.app.store import PostgresInventoryStore

DSN = os.environ.get("INVENTORY_TEST_DSN")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DSN, reason="INVENTORY_TEST_DSN not set"),
]


def test_reserve_is_bounded_by_stock():
    store = PostgresInventoryStore(DSN, max_size=2)
    try:
        store.ensure_schema()
        before = store.get_stock("sku-cherry")
        assert before is not None
        assert store.reserve("sku-cherry", before) is True
        assert store.get_stock("sku-cherry") == 0
        assert store.reserve("sku-cherry", 1) is False  # no negative stock
        assert store.reserve("no-such-sku", 1) is False
    finally:
        store.close()
