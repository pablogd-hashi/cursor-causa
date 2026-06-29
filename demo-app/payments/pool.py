"""A toy async connection pool — the home of the demo's regression.

The whole incident hinges on one number: ``POOL_MAX_SIZE``. ``acquire()`` blocks
on an ``asyncio.Semaphore`` sized by it, so if the pool is too small for the
offered concurrency, callers queue, wait time climbs, and request latency tracks
the wait. Lowering ``POOL_MAX_SIZE`` (in production, via a PR; in the live demo,
via the ``POOL_MAX_SIZE`` env var that ``break.sh`` sets) reproduces the 02:14
pool-exhaustion incident.

The pool emits three metrics that make the cause visible in Grafana:
- ``payments_pool_wait_seconds`` (histogram) — time blocked waiting to acquire.
- ``payments_pool_inuse`` (gauge) — connections currently checked out.
- ``payments_pool_max`` (gauge) — the configured ceiling, so a dashboard can show
  the pool pinned at its maximum.
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager

from opentelemetry.metrics import CallbackOptions, Observation

from .telemetry import get_meter

# The breakable knob. Read once at import. Default is the healthy value; the
# regression is lowering this (or setting the env var) to a number below the
# service's normal concurrency.
POOL_MAX_SIZE = int(os.getenv("POOL_MAX_SIZE", "10"))


class ConnectionPool:
    """Bounded async pool. ``max_size`` defaults to the module-level
    ``POOL_MAX_SIZE`` so a revert of that constant (or the env override) changes
    the pool size without touching this class."""

    def __init__(self, max_size: int | None = None) -> None:
        self.max_size = max_size if max_size is not None else POOL_MAX_SIZE
        self._sem = asyncio.Semaphore(self.max_size)
        self._in_use = 0

        meter = get_meter("payments.pool")
        self._wait = meter.create_histogram(
            "payments_pool_wait_seconds",
            description="Time spent waiting to acquire a pooled connection",
        )
        # Observable gauges are read at collection time via these callbacks.
        meter.create_observable_gauge(
            "payments_pool_inuse",
            callbacks=[self._observe_in_use],
            description="Connections currently checked out of the pool",
        )
        meter.create_observable_gauge(
            "payments_pool_max",
            callbacks=[self._observe_max],
            description="Configured maximum pool size",
        )

    def _observe_in_use(self, options: CallbackOptions):
        yield Observation(self._in_use)

    def _observe_max(self, options: CallbackOptions):
        yield Observation(self.max_size)

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection, recording how long the caller had to wait."""
        start = time.perf_counter()
        async with self._sem:
            self._wait.record(time.perf_counter() - start)
            self._in_use += 1
            try:
                yield
            finally:
                self._in_use -= 1
