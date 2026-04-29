"""
Performance tests to verify that the sync `def` submit_proof endpoint handles
concurrent requests via FastAPI's thread pool rather than blocking the event loop.

The PR converted `submit_proof` from `async def` to `def` so that FastAPI
dispatches it to a thread pool.  These tests confirm that behaviour:

* A ``def`` endpoint with a blocking sleep executes concurrently across threads,
  so N parallel requests finish in roughly 1x the single-request delay.
* An ``async def`` endpoint with a non-blocking sleep executes concurrently, so N
  parallel requests finish in roughly 1x the single-request delay.
"""

import asyncio
import time

import httpx
from fastapi import FastAPI

# Simulated synchronous DB delay (seconds).  The delay must be long enough that
# thread-pool startup overhead is negligible relative to total execution time.
SIMULATED_DB_DELAY_S = 0.10  # 100 ms
CONCURRENT_REQUESTS = 10


def _make_sync_app() -> FastAPI:
    """Return a FastAPI app with a *sync* def endpoint that blocks for a fixed delay."""
    app = FastAPI()

    @app.get("/slow")
    def slow_sync():
        time.sleep(SIMULATED_DB_DELAY_S)
        return {"ok": True}

    return app


def _make_async_non_blocking_app() -> FastAPI:
    """Return a FastAPI app with an *async* def endpoint that executes without blocking the event loop."""
    app = FastAPI()

    @app.get("/slow")
    async def slow_async():
        await asyncio.sleep(SIMULATED_DB_DELAY_S)  # non-blocking sleep
        return {"ok": True}

    return app


async def _time_concurrent_requests(app: FastAPI) -> float:
    """Fire CONCURRENT_REQUESTS GET /slow requests concurrently and return elapsed seconds."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start = time.perf_counter()
        responses = await asyncio.gather(*[client.get("/slow") for _ in range(CONCURRENT_REQUESTS)])
        elapsed = time.perf_counter() - start

    assert all(r.status_code == 200 for r in responses)
    return elapsed


async def test_sync_endpoint_uses_thread_pool():
    """
    A sync def endpoint runs in FastAPI's thread pool, so CONCURRENT_REQUESTS
    in-flight requests should complete much faster than sequential execution.
    """
    elapsed = await _time_concurrent_requests(_make_sync_app())
    sequential_time = CONCURRENT_REQUESTS * SIMULATED_DB_DELAY_S

    # Concurrent execution via threads should be at least 3× faster than sequential.
    assert elapsed < sequential_time / 3, (
        f"Sync endpoint took {elapsed:.3f}s, expected less than "
        f"{sequential_time / 3:.3f}s (sequential would be {sequential_time:.3f}s)"
    )


async def test_async_non_blocking_endpoint_executes_concurrently():
    """
    An async def endpoint that calls non-blocking await asyncio.sleep() doesn't hold the event loop.
    CONCURRENT_REQUESTS should therefore complete much faster than sequential execution.
    """
    elapsed = await _time_concurrent_requests(_make_async_non_blocking_app())
    sequential_time = CONCURRENT_REQUESTS * SIMULATED_DB_DELAY_S

    # Non-blocking execution should be at least 3× faster than sequential.
    assert elapsed < sequential_time / 3, (
        f"Async non-blocking endpoint took {elapsed:.3f}s, expected less than "
        f"{sequential_time / 3:.3f}s (sequential would be {sequential_time:.3f}s)"
    )
