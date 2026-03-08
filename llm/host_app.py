from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import time
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

try:
    import orjson  # noqa: F401
    from fastapi.responses import ORJSONResponse

    DefaultResponseClass = ORJSONResponse
except ImportError:  # pragma: no cover - optional speedup
    DefaultResponseClass = JSONResponse

try:
    from .engine_pool import EnginePool
    from .engine_eval import EngineEvaluator
    from .elite_engine_service import EliteEngineService
    from .metrics import miss_metrics_snapshot, record_miss_sample
    from .opening_book import OpeningBook
    from .position_input import normalize_fen
    from .predictive_cache import get_predictions
    from .redis_client import (
        close_redis,
        get_redis_info,
        get_redis_keys,
        get_redis_value,
        redis_client,
        redis_backend_name,
        redis_is_available,
        verify_redis_connection,
    )
except ImportError:
    from engine_pool import EnginePool
    from engine_eval import EngineEvaluator
    from elite_engine_service import EliteEngineService
    from metrics import miss_metrics_snapshot, record_miss_sample
    from opening_book import OpeningBook
    from position_input import normalize_fen
    from predictive_cache import get_predictions
    from redis_client import (
        close_redis,
        get_redis_info,
        get_redis_keys,
        get_redis_value,
        redis_client,
        redis_backend_name,
        redis_is_available,
        verify_redis_connection,
    )

if os.name == "nt" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    current_policy = asyncio.get_event_loop_policy()
    if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(default_response_class=DefaultResponseClass)
engine_pool = EnginePool(size=int(os.getenv("ENGINE_POOL_SIZE", "2")))
engine_eval = EngineEvaluator(engine_pool)
opening_book = OpeningBook()
engine_service = EliteEngineService(engine_eval, opening_book=opening_book)


class EngineEvalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fen: str | None = None
    moves: list[str] = Field(default_factory=list)
    movetime_ms: int | None = Field(
        default=None,
        validation_alias=AliasChoices("movetime_ms", "movetime"),
    )
    nodes: int | None = None

    @property
    def movetime(self) -> int | None:
        return self.movetime_ms
def _resolve_request_limits(
    *,
    movetime: int | None,
    nodes: int | None,
) -> tuple[int | None, int | None]:
    return engine_eval.resolve_limits(movetime=movetime, nodes=nodes)


@app.get("/")
def root():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    await verify_redis_connection()
    await engine_pool.start()


@app.on_event("shutdown")
async def shutdown():
    await engine_pool.stop()
    opening_book.close()
    await close_redis()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "engine_pool_available": engine_pool.available,
        "engine_pool_capacity": engine_pool.capacity,
        "opening_book_available": opening_book.available,
        "opening_book_path": opening_book.path if opening_book.available else None,
        "redis_backend": redis_backend_name(),
        "redis_available": await redis_is_available(),
    }


@app.get("/debug/redis")
async def debug_redis():
    if redis_client is None:
        return {
            "backend": redis_backend_name(),
            "redis": False,
            "detail": "client_unavailable",
        }
    try:
        pong = await redis_client.ping()
        return {
            "backend": redis_backend_name(),
            "redis": bool(pong),
            "pong": pong,
        }
    except Exception as exc:
        return {
            "backend": redis_backend_name(),
            "redis": False,
            "detail": str(exc),
        }


@app.get("/debug/book")
async def debug_book():
    return {
        "available": opening_book.available,
        "path": opening_book.path,
    }


@app.post("/engine/eval")
async def eval_position(payload: EngineEvalRequest):
    movetime, nodes = _resolve_request_limits(movetime=payload.movetime_ms, nodes=payload.nodes)
    result = await _evaluate_position(
        fen=payload.fen,
        moves=payload.moves,
        movetime=movetime,
        nodes=nodes,
    )
    return result


@app.get("/engine/eval")
async def eval_position_query(
    fen: str | None = None,
    moves: list[str] | None = Query(default=None),
    movetime_ms: int | None = None,
    movetime: int | None = None,
    nodes: int | None = None,
):
    requested_movetime = movetime_ms if movetime_ms is not None else movetime
    movetime, nodes = _resolve_request_limits(movetime=requested_movetime, nodes=nodes)
    result = await _evaluate_position(
        fen=fen,
        moves=moves or [],
        movetime=movetime,
        nodes=nodes,
    )
    return result


async def _evaluate_position(
    *,
    fen: str | None,
    moves: list[str] | None,
    movetime: int | None,
    nodes: int | None,
):
    result, metrics = await engine_service.evaluate_with_metrics(
        fen=fen,
        moves=moves,
        movetime=movetime,
        nodes=nodes,
    )
    if not metrics.get("cache_hit", True):
        record_miss_sample(metrics)
    return {
        **result,
        "_metrics": metrics,
    }


@app.get("/debug/engine")
async def debug_engine():
    capacity = engine_pool.capacity
    available = engine_pool.available
    return {
        "pool_size": capacity,
        "available": available,
        "busy": max(0, capacity - available),
    }


@app.post("/debug/engine-raw")
async def engine_raw(payload: EngineEvalRequest):
    movetime, nodes = _resolve_request_limits(movetime=payload.movetime_ms, nodes=payload.nodes)
    started = time.perf_counter()
    engine = await engine_pool.acquire()
    wait_ms = round((time.perf_counter() - started) * 1000, 3)

    try:
        eval_started = time.perf_counter()
        result = await engine_eval.evaluate_with_engine(
            engine,
            payload.fen,
            moves=payload.moves,
            movetime=movetime,
            nodes=nodes,
        )
        eval_ms = round((time.perf_counter() - eval_started) * 1000, 3)
    finally:
        await engine_pool.release(engine)

    total_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        **result,
        "_metrics": {
            "engine_wait_ms": wait_ms,
            "engine_eval_ms": eval_ms,
            "total_ms": total_ms,
        },
    }


@app.get("/debug/cache")
async def debug_cache(pattern: str = "cc:*"):
    stats = await get_redis_info("stats")
    return {
        "backend": redis_backend_name(),
        "pattern": pattern,
        "keys": await get_redis_keys(pattern),
        "hits": stats.get("keyspace_hits", 0),
        "misses": stats.get("keyspace_misses", 0),
        "stats": stats,
    }


@app.get("/debug/cache/value")
async def debug_cache_value(key: str):
    return {
        "backend": redis_backend_name(),
        "key": key,
        "value": await get_redis_value(key),
    }


@app.get("/debug/miss-metrics")
def debug_miss_metrics():
    return miss_metrics_snapshot()


@app.get("/engine/predictions")
async def engine_predictions(fen: str):
    normalized_fen = normalize_fen(fen) or fen
    return {
        "fen": normalized_fen,
        "predictions": await get_predictions(normalized_fen),
    }


if __name__ == "__main__":
    import uvicorn

    app_path = "host_app:app" if __package__ in (None, "") else "llm.host_app:app"
    uvicorn.run(
        app_path,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=max(1, int(os.getenv("UVICORN_WORKERS", "4"))),
    )
