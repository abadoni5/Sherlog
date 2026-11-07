"""Persistence for payments. The app depends on `ChargeStore`, not on Postgres,
so unit tests can swap in a fake and never need a database."""

import os
from typing import Protocol

from psycopg_pool import ConnectionPool

SCHEMA = """
CREATE TABLE IF NOT EXISTS charges (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id     TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency     TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class ChargeStore(Protocol):
    def insert_charge(self, order_id: str, amount_cents: int, currency: str) -> str:
        """Persist a charge and return its id."""
        ...

    def close(self) -> None: ...


class PostgresStore:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10,
                 timeout: float = 5.0) -> None:
        self._pool = ConnectionPool(dsn, min_size=min_size, max_size=max_size,
                                    timeout=timeout, open=True)
        self._pool.wait()

    @classmethod
    def from_env(cls) -> "PostgresStore":
        return cls(
            dsn=os.environ["PAYMENTS_DB_DSN"],
            max_size=int(os.environ.get("PAYMENTS_DB_POOL_MAX", "10")),
        )

    def ensure_schema(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(SCHEMA)

    def insert_charge(self, order_id: str, amount_cents: int, currency: str) -> str:
        with self._pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO charges (order_id, amount_cents, currency) "
                "VALUES (%s, %s, %s) RETURNING id",
                (order_id, amount_cents, currency),
            ).fetchone()
        return str(row[0])

    def close(self) -> None:
        self._pool.close()
