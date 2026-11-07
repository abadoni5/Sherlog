"""Needs a real Postgres. Set PAYMENTS_TEST_DSN, e.g.
postgresql://postgres:postgres@localhost:5433/postgres
Run with: uv run pytest -m integration"""
import os

import psycopg
import pytest

from fake_system.payments.app.store import PostgresStore

DSN = os.environ.get("PAYMENTS_TEST_DSN")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DSN, reason="PAYMENTS_TEST_DSN not set"),
]


def test_insert_charge_roundtrip():
    store = PostgresStore(DSN, max_size=2)
    try:
        store.ensure_schema()
        charge_id = store.insert_charge("order-1", 1234, "USD")
        with psycopg.connect(DSN) as conn:
            row = conn.execute(
                "SELECT order_id, amount_cents, currency FROM charges WHERE id = %s",
                (charge_id,),
            ).fetchone()
        assert row == ("order-1", 1234, "USD")
    finally:
        store.close()
