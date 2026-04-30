import asyncio
import time
from fastapi import FastAPI
import httpx

SIMULATED_DB_DELAY_S = 0.10
CONCURRENT_REQUESTS = 10


def _make_async_blocking_app() -> FastAPI:
    app = FastAPI()

    @app.get("/slow")
    async def slow_async():
        time.sleep(SIMULATED_DB_DELAY_S)
        return {"ok": True}

    return app


def _make_async_non_blocking_app() -> FastAPI:
    app = FastAPI()

    @app.get("/slow")
    async def slow_async():
        await asyncio.sleep(SIMULATED_DB_DELAY_S)
        return {"ok": True}

    return app


async def _time_concurrent_requests(app: FastAPI) -> float:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start = time.perf_counter()
        responses = await asyncio.gather(
            *[client.get("/slow") for _ in range(CONCURRENT_REQUESTS)]
        )
        elapsed = time.perf_counter() - start
    assert all(r.status_code == 200 for r in responses)
    return elapsed


async def main():
    elapsed_block = await _time_concurrent_requests(_make_async_blocking_app())
    print(f"Blocking: {elapsed_block:.3f}s")
    elapsed_nonblock = await _time_concurrent_requests(_make_async_non_blocking_app())
    print(f"Non-blocking: {elapsed_nonblock:.3f}s")


asyncio.run(main())
