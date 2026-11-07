"""FastAPI helpers shared by all services."""

import logging
import time
import uuid

from fastapi import FastAPI, Request


def add_request_logging(app: FastAPI, log: logging.Logger) -> None:
    """Log one `request_completed` line per request and propagate a request id
    (taken from the x-request-id header, or generated)."""

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        log.info(
            "request completed",
            extra={
                "event": "request_completed",
                "route": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                "request_id": request_id,
            },
        )
        return response
