"""The oracle test for the pool-exhaustion incident.

This is the test the Cursor Cloud Agent is asked to run on current code vs
reverted code. It instantiates the pool exactly as the app does (``ConnectionPool()``
with no argument), so its size follows whichever lever produced the incident:

- the committed ``POOL_MAX_SIZE`` default in ``payments/pool.py`` (a code revert
  flips the result), or
- the ``POOL_MAX_SIZE`` environment variable (the live ``break.sh`` lever).

It fires ``CONCURRENCY`` charges at once and checks the p95 of acquire+work
latency. With a healthy pool everything runs in parallel and p95 is ~one unit of
work; with a small pool the calls queue and p95 climbs past the threshold.
"""

from __future__ import annotations

import asyncio
import time

from payments.pool import ConnectionPool

HOLD_S = 0.05  # simulated work while holding a connection
CONCURRENCY = 40  # callers firing at once
P95_THRESHOLD_S = 0.15  # healthy p95 ceiling


async def _one_call(pool: ConnectionPool) -> float:
    start = time.perf_counter()
    async with pool.acquire():
        await asyncio.sleep(HOLD_S)
    return time.perf_counter() - start


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[int(0.95 * (len(ordered) - 1))]


def test_pool_exhaustion():
    async def run() -> tuple[int, float]:
        pool = ConnectionPool()  # size follows POOL_MAX_SIZE (env or code default)
        latencies = await asyncio.gather(*[_one_call(pool) for _ in range(CONCURRENCY)])
        return pool.max_size, _p95(list(latencies))

    max_size, p95 = asyncio.run(run())
    assert p95 < P95_THRESHOLD_S, (
        f"p95 acquire+work latency {p95:.3f}s exceeds {P95_THRESHOLD_S}s "
        f"at pool size {max_size} under {CONCURRENCY} concurrent callers"
    )
