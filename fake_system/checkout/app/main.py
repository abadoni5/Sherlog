import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from fake_system.common.logs import get_logger
from fake_system.common.web import add_request_logging

SERVICE = "checkout"


class CheckoutRequest(BaseModel):
    order_id: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    amount_cents: int = Field(gt=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


def _build_clients() -> tuple[httpx.Client, httpx.Client]:
    timeout = float(os.environ.get("CHECKOUT_DOWNSTREAM_TIMEOUT", "2.0"))
    return (
        httpx.Client(base_url=os.environ["INVENTORY_URL"], timeout=timeout),
        httpx.Client(base_url=os.environ["PAYMENTS_URL"], timeout=timeout),
    )


def create_app(inventory: httpx.Client | None = None,
               payments: httpx.Client | None = None,
               logger: logging.Logger | None = None) -> FastAPI:
    """Tests inject clients backed by httpx.MockTransport; in the container
    they are built from env vars at startup."""
    log = logger or get_logger(SERVICE)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if inventory is None or payments is None:
            app.state.inventory, app.state.payments = _build_clients()
        else:
            app.state.inventory, app.state.payments = inventory, payments
        yield
        app.state.inventory.close()
        app.state.payments.close()

    app = FastAPI(title="checkout", lifespan=lifespan)
    add_request_logging(app, log)

    def call(dependency: str, client: httpx.Client, path: str, payload: dict,
             request_id: str) -> httpx.Response:
        """POST to a downstream service, logging duration and failures."""
        start = time.perf_counter()
        extra = {"event": "downstream_call", "dependency": dependency,
                 "route": path, "request_id": request_id}
        try:
            resp = client.post(path, json=payload,
                               headers={"x-request-id": request_id})
        except httpx.HTTPError:
            extra.update(event="downstream_failed",
                         duration_ms=round((time.perf_counter() - start) * 1000, 1))
            log.error(f"{dependency} call failed", exc_info=True, extra=extra)
            raise HTTPException(status_code=502, detail=f"{dependency} unavailable")
        extra.update(status=resp.status_code,
                     duration_ms=round((time.perf_counter() - start) * 1000, 1))
        log.info(f"{dependency} responded", extra=extra)
        return resp

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/checkout")
    def checkout(body: CheckoutRequest, request: Request) -> dict:
        rid = request.state.request_id

        reserved = call("inventory", request.app.state.inventory, "/reserve",
                        {"sku": body.sku, "quantity": body.quantity}, rid)
        if reserved.status_code == 409:
            raise HTTPException(status_code=409, detail="out of stock")
        if reserved.status_code != 200:
            raise HTTPException(status_code=502, detail="inventory error")

        charged = call("payments", request.app.state.payments, "/charge",
                       {"order_id": body.order_id, "amount_cents": body.amount_cents,
                        "currency": body.currency}, rid)
        if charged.status_code != 200:
            # Simple failure handling: stock stays reserved (no compensation yet).
            log.error("payment failed", extra={"event": "checkout_failed",
                      "route": "/checkout", "request_id": rid,
                      "order_id": body.order_id, "payments_status": charged.status_code})
            raise HTTPException(status_code=502, detail="payment failed")

        log.info("checkout completed", extra={"event": "checkout_completed",
                 "route": "/checkout", "request_id": rid, "order_id": body.order_id})
        return {"order_id": body.order_id,
                "charge_id": charged.json()["charge_id"], "status": "completed"}

    return app


app = create_app()
