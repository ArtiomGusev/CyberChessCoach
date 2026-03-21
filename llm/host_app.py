import asyncio
import logging
import os
import time
from typing import List, Tuple

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

_API_KEY = os.getenv("SECA_API_KEY")
_IS_PROD = os.getenv("SECA_ENV", "dev") in {"prod", "production"}


def verify_api_key(x_api_key: str = Header(None)):
    """Guard debug endpoints — mirrors server.py:verify_api_key."""
    if _API_KEY is None:
        if _IS_PROD:
            raise HTTPException(status_code=500, detail="Server misconfiguration")
        return  # dev mode: unauthenticated access allowed
    if x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# --- Response Class Setup ---
try:
    import orjson  # noqa: F401
    from fastapi.responses import ORJSONResponse

    DefaultResponseClass = ORJSONResponse
except ImportError:
    DefaultResponseClass = JSONResponse

# --- Internal Imports ---
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

# --- Event Loop Policy ---
if os.name == "nt" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    current_policy = asyncio.get_event_loop_policy()
    if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

_limiter = Limiter(key_func=get_remote_address)

app = FastAPI(default_response_class=DefaultResponseClass)
app.state.limiter = _limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "Too many requests"})


# Global Exception Handler for Security (CWE-209)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error") 
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}, 
    )


# Initialize Services
engine_pool = EnginePool(size=int(os.getenv("ENGINE_POOL_SIZE", "2")))
engine_eval = EngineEvaluator(engine_pool)
opening_book = OpeningBook()
engine_service = EliteEngineService(engine_eval, opening_book=opening_book)


class EngineEvalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fen: str | None = None
    moves: List[str] = Field(default_factory=list)
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
) -> Tuple[int | None, int | None]:
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
async def debug_redis(_: None = Depends(verify_api_key)):
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
    except Exception:
        logger.exception("Redis connection error during debug check")

        return {
            "backend": redis_backend_name(),
            "redis": False,
            "detail": "Redis connection unavailable",
        }


@app.get("/debug/book")
async def debug_book(_: None = Depends(verify_api_key)):
    return {
        "available": opening_book.available,
        "path": opening_book.path,
    }


@app.post("/engine/eval")
@_limiter.limit("30/minute")
async def eval_position(request: Request, payload: EngineEvalRequest):
    movetime, nodes = _resolve_request_limits(movetime=payload.movetime_ms, nodes=payload.nodes)
    return await _evaluate_position(
        fen=payload.fen,
        moves=payload.moves,
        movetime=movetime,
        nodes=nodes,
    )


@app.get("/engine/eval")
@_limiter.limit("30/minute")
async def eval_position_query(
    request: Request,
    fen: str | None = None,
    moves: List[str] | None = Query(default=None),
    movetime_ms: int | None = None,
    movetime: int | None = None,
    nodes: int | None = None,
):
    req_movetime = movetime_ms if movetime_ms is not None else movetime
    m_time, n_nodes = _resolve_request_limits(movetime=req_movetime, nodes=nodes)
    return await _evaluate_position(
        fen=fen,
        moves=moves or [],
        movetime=m_time,
        nodes=n_nodes,
    )


async def _evaluate_position(
    *,
    fen: str | None,
    moves: List[str] | None,
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
async def debug_engine(_: None = Depends(verify_api_key)):
    capacity = engine_pool.capacity
    available = engine_pool.available
    return {
        "pool_size": capacity,
        "available": available,
        "busy": max(0, capacity - available),
    }


@app.post("/debug/engine-raw")
async def engine_raw(payload: EngineEvalRequest, _: None = Depends(verify_api_key)):
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
async def debug_cache(pattern: str = "cc:*", _: None = Depends(verify_api_key)):
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
async def debug_cache_value(key: str, _: None = Depends(verify_api_key)):
    return {
        "backend": redis_backend_name(),
        "key": key,
        "value": await get_redis_value(key),
    }


@app.get("/debug/miss-metrics")
def debug_miss_metrics(_: None = Depends(verify_api_key)):
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

    # Use string to avoid import issues in some environments
    U_APP = "host_app:app" if __package__ in (None, "") else "llm.host_app:app"
    uvicorn.run(
        U_APP,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=max(1, int(os.getenv("UVICORN_WORKERS", "4"))),
    )
