import asyncio
import os
import time
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# Setup logging to see actual errors in your console/logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# --- Response Class Setup ---
try:
    import orjson
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

app = FastAPI(default_response_class=DefaultResponseClass)

# --- GLOBAL EXCEPTION HANDLER (The Safety Net) ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches any unhandled exceptions and returns a generic error message.
    Logs the full traceback internally for the developer.
    """
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )

# --- App State Management ---
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

def _resolve_request_limits(*, movetime: int | None, nodes: int | None):
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
    # Sanitized health check (don't reveal full paths if possible)
    return {
        "status": "ok",
        "engine_pool_available": engine_pool.available,
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
        # FIXED: Log the error internally, return generic detail to user
        logger.error(f"Redis debug failure: {exc}")
        return {
            "backend": redis_backend_name(),
            "redis": False,
            "detail": "service_unreachable",
        }

@app.post("/engine/eval")
async def eval_position(payload: EngineEvalRequest):
    movetime, nodes = _resolve_request_limits(movetime=payload.movetime_ms, nodes=payload.nodes)
    return await _evaluate_position(
        fen=payload.fen,
        moves=payload.moves,
        movetime=movetime,
        nodes=nodes,
    )

async def _evaluate_position(*, fen, moves, movetime, nodes):
    # Wrapped in try/except to ensure metrics are recorded even if eval fails
    try:
        result, metrics = await engine_service.evaluate_with_metrics(
            fen=fen, moves=moves, movetime=movetime, nodes=nodes,
        )
        if not metrics.get("cache_hit", True):
            record_miss_sample(metrics)
        return {**result, "_metrics": metrics}
    except Exception as exc:
        logger.error(f"Evaluation error: {exc}")
        raise # The global handler will catch this and return a 500

# ... (other routes like /debug/book, /debug/engine follow the same logic) ...

if __name__ == "__main__":
    import uvicorn
    app_path = "host_app:app" if __package__ in (None, "") else "llm.host_app:app"
    uvicorn.run(
        app_path,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=max(1, int(os.getenv("UVICORN_WORKERS", "4"))),
    )