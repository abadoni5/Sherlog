import os
from typing import Protocol

from psycopg_pool import ConnectionPool

SCHEMA = """
CREATE TABLE IF NOT EXISTS stock (
    sku      TEXT PRIMARY KEY,
    quantity INTEGER NOT NULL CHECK (quantity >= 0)
)
"""
SEED = [("sku-apple", 1_000_000), ("sku-banana", 1_000_000), ("sku-cherry", 5)]


class InventoryStore(Protocol):
    def get_stock(self, sku: str) -> int | None:
        """Quantity on hand, or None for an unknown sku."""
        ...

    def reserve(self, sku: str, quantity: int) -> bool:
        """Atomically take `quantity` units. False if unknown or insufficient."""
        ...

    def close(self) -> None: ...


class PostgresInventoryStore:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10,
                 timeout: float = 5.0) -> None:
        self._pool = ConnectionPool(dsn, min_size=min_size, max_size=max_size,
                                    timeout=timeout, open=True)
        self._pool.wait()

    @classmethod
    def from_env(cls) -> "PostgresInventoryStore":
        return cls(
            dsn=os.environ["INVENTORY_DB_DSN"],
            max_size=int(os.environ.get("INVENTORY_DB_POOL_MAX", "10")),
        )

    def ensure_schema(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(SCHEMA)
            for sku, qty in SEED:
                conn.execute(
                    "INSERT INTO stock (sku, quantity) VALUES (%s, %s) "
                    "ON CONFLICT (sku) DO NOTHING",
                    (sku, qty),
                )

    def get_stock(self, sku: str) -> int | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT quantity FROM stock WHERE sku = %s", (sku,)
            ).fetchone()
        return row[0] if row else None

    def reserve(self, sku: str, quantity: int) -> bool:
        # One conditional UPDATE: the check and the decrement are atomic, so
        # concurrent reservations can never drive stock below zero.
        with self._pool.connection() as conn:
            row = conn.execute(
                "UPDATE stock SET quantity = quantity - %s "
                "WHERE sku = %s AND quantity >= %s RETURNING quantity",
                (quantity, sku, quantity),
            ).fetchone()
        return row is not None

    def close(self) -> None:
        self._pool.close()
