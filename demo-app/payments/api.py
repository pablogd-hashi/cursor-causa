"""The payments service: a single ``/charge`` endpoint that holds a pooled
connection across a simulated database write and external-processor call.

The execution path the investigation cares about is deliberately short and real:
``charge`` -> ``ConnectionPool.acquire`` -> work-while-holding. When the pool is
undersized, ``acquire`` blocks and the handler's measured duration climbs, which
is exactly what the ``payments_request_duration_seconds`` histogram and the
``PaymentsHighLatencyP99`` alert pick up.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from fastapi import FastAPI

# Telemetry must be initialised before the app is instrumented and before the
# pool creates its instruments, so the global MeterProvider is in place.
from .telemetry import get_meter, init_telemetry

init_telemetry(os.environ.get("OTEL_SERVICE_NAME", "payments"))

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: E402

from .pool import ConnectionPool  # noqa: E402

log = logging.getLogger("payments")

# Normal per-request service time held while a connection is checked out: a
# simulated DB write plus a downstream card-processor call (~100ms total, which
# is realistic for a payment). This is steady-state behaviour, not the
# regression — the regression is the pool size. A pool of 50 absorbs the offered
# concurrency at this service time; a pool of 10 makes requests queue.
DB_WRITE_S = float(os.getenv("DB_WRITE_S", "0.03"))
EXT_CALL_S = float(os.getenv("EXT_CALL_S", "0.07"))

app = FastAPI(title="payments")
pool = ConnectionPool()

_meter = get_meter("payments.api")
_req_duration = _meter.create_histogram(
    "payments_request_duration_seconds",
    description="End-to-end duration of the charge handler",
)


async def _pooled_work(amount: float = 1.0) -> dict:
    """Shared handler body: acquire a pool slot and hold it across simulated work."""
    start = time.perf_counter()
    async with pool.acquire():
        await asyncio.sleep(DB_WRITE_S + EXT_CALL_S)
    duration = time.perf_counter() - start
    _req_duration.record(duration)
    return {"status": "ok", "amount": amount, "duration_s": round(duration, 4)}


@app.get("/")
async def root():
    # Mesh traffic (web → api → payments) hits / like fake-service; same pool path.
    return await _pooled_work()


@app.post("/charge")
async def charge(amount: float = 1.0):
    return await _pooled_work(amount)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "pool_max": pool.max_size}


FastAPIInstrumentor.instrument_app(app)
