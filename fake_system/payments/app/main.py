import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from fake_system.common.logs import get_logger
from fake_system.common.web import add_request_logging
from fake_system.payments.app.store import ChargeStore, PostgresStore

SERVICE = "payments"


class ChargeRequest(BaseModel):
    order_id: str = Field(min_length=1)
    amount_cents: int = Field(gt=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class ChargeResponse(BaseModel):
    charge_id: str
    status: str


def create_app(store: ChargeStore | None = None,
               logger: logging.Logger | None = None) -> FastAPI:
    """App factory. Tests inject a fake store and a capturing logger; in the
    container both are built from environment variables at startup."""
    log = logger or get_logger(SERVICE)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if store is None:
            real = PostgresStore.from_env()
            real.ensure_schema()
            app.state.store = real
        else:
            app.state.store = store
        yield
        app.state.store.close()

    app = FastAPI(title="payments", lifespan=lifespan)

    add_request_logging(app, log)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    # Plain `def` (not async): FastAPI runs it in a threadpool, which suits
    # the blocking psycopg pool.
    @app.post("/charge", response_model=ChargeResponse)
    def charge(body: ChargeRequest, request: Request) -> ChargeResponse:
        request_id = request.state.request_id
        try:
            charge_id = request.app.state.store.insert_charge(
                body.order_id, body.amount_cents, body.currency
            )
        except Exception:
            log.exception(
                "charge failed",
                extra={"event": "charge_failed", "route": "/charge",
                       "request_id": request_id, "order_id": body.order_id},
            )
            raise HTTPException(status_code=500, detail="charge failed")
        log.info(
            "charge succeeded",
            extra={"event": "charge_succeeded", "route": "/charge",
                   "request_id": request_id, "order_id": body.order_id,
                   "amount_cents": body.amount_cents},
        )
        return ChargeResponse(charge_id=charge_id, status="succeeded")

    return app


# Entry point for uvicorn: `uvicorn fake_system.payments.app.main:app`.
# Safe to import without a database: the store is only built at startup.
app = create_app()
