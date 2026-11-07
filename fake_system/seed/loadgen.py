"""Steady background traffic: mostly valid checkouts, some out-of-stock
rejections and health checks, so logs have realistic noise."""

import os
import random
import sys
import time
import uuid

import httpx

# (weight, kind). Out-of-stock hits the 5-unit "sku-cherry" with a bigger quantity.
MIX = [(85, "checkout"), (5, "out_of_stock"), (10, "health")]


def next_request(rng: random.Random) -> tuple[str, str, dict | None]:
    kind = rng.choices([k for _, k in MIX], weights=[w for w, _ in MIX])[0]
    if kind == "health":
        return "GET", "/health", None
    order = {"order_id": f"order-{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}",
             "sku": rng.choice(["sku-apple", "sku-banana"]), "quantity": 1,
             "amount_cents": rng.choice([499, 1299, 2500, 8900]), "currency": "USD"}
    if kind == "out_of_stock":
        order.update(sku="sku-cherry", quantity=50)
    return "POST", "/checkout", order


def run(base_url: str, rps: float, seed: int = 0, duration: float | None = None) -> None:
    rng = random.Random(seed)
    deadline = None if duration is None else time.monotonic() + duration
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        while deadline is None or time.monotonic() < deadline:
            method, path, body = next_request(rng)
            try:
                client.request(method, path, json=body)
            except httpx.HTTPError as exc:
                print(f"loadgen: {method} {path} failed: {exc!r}", file=sys.stderr)
            time.sleep(1.0 / rps)


if __name__ == "__main__":
    run(os.environ.get("CHECKOUT_URL", "http://localhost:8001"),
        rps=float(os.environ.get("LOADGEN_RPS", "2")),
        seed=int(os.environ.get("LOADGEN_SEED", "0")))
