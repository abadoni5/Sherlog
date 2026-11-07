import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from fake_system.common.logs import get_logger
from fake_system.common.web import add_request_logging
from fake_system.inventory.app.store import InventoryStore, PostgresInventoryStore

SERVICE = "inventory"


class ReserveRequest(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)


def create_app(store: InventoryStore | None = None,
               logger: logging.Logger | None = None) -> FastAPI:
    log = logger or get_logger(SERVICE)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if store is None:
            real = PostgresInventoryStore.from_env()
            real.ensure_schema()
            app.state.store = real
        else:
            app.state.store = store
        yield
        app.state.store.close()

    app = FastAPI(title="inventory", lifespan=lifespan)
    add_request_logging(app, log)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/stock/{sku}")
    def stock(sku: str, request: Request) -> dict:
        quantity = request.app.state.store.get_stock(sku)
        if quantity is None:
            raise HTTPException(status_code=404, detail="unknown sku")
        return {"sku": sku, "quantity": quantity}

    @app.post("/reserve")
    def reserve(body: ReserveRequest, request: Request) -> dict:
        ok = request.app.state.store.reserve(body.sku, body.quantity)
        if not ok:
            log.warning(
                "reservation rejected",
                extra={"event": "reserve_rejected", "route": "/reserve",
                       "request_id": request.state.request_id,
                       "sku": body.sku, "quantity": body.quantity},
            )
            raise HTTPException(status_code=409, detail="insufficient stock")
        log.info(
            "stock reserved",
            extra={"event": "stock_reserved", "route": "/reserve",
                   "request_id": request.state.request_id,
                   "sku": body.sku, "quantity": body.quantity},
        )
        return {"sku": body.sku, "reserved": body.quantity}

    return app


app = create_app()
