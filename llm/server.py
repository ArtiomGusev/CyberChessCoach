import logging
import os
import shutil
import chess
import time
import threading
from functools import lru_cache
from typing import Literal
from fastapi import FastAPI, Header, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from llm.seca.shared_limiter import limiter
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

try:
    from .player_api import router as player_router
except ImportError:
    # Supports top-level module execution (e.g. `uvicorn server:app`)
    from player_api import router as player_router
from llm.seca.auth.router import router as auth_router, get_current_player
from llm.seca.events.router import router as game_router
from llm.seca.curriculum.router import router as curriculum_router
from llm.seca.inference.router import router as inference_router

# register SECA models
import llm.seca.events.models

from llm.seca.engines.stockfish.pool import (
    EnginePoolSettings,
    FenMoveCache,
    StockfishEnginePool,
)
from llm.rag.engine_signal.extract_engine_signal import extract_engine_signal
from llm.explain_pipeline import generate_validated_explanation
from llm.rag.validators.explain_response_schema import (
    validate_explain_response,
    ExplainSchemaError,
)
from llm.rag.prompts.input_sanitizer import sanitize_user_query
from llm.seca.learning.outcome_tracker import ExplanationOutcomeTracker
from llm.seca.learning.skill_update import SkillState
from llm.seca.adaptation.coupling import compute_adaptation
from llm.seca.curriculum.scheduler import CurriculumScheduler
from llm.seca.curriculum.types import Weakness
from llm.seca.storage.db import init_db
from llm.seca.storage.event_store import EventStore
from llm.seca.skill.pipeline import SkillPipeline
from llm.seca.world_model.safe_stub import SafeWorldModel
from llm.seca.explainer.safe_explainer import SafeExplainer
from llm.seca.safety.freeze import enforce
from llm.seca.runtime.safe_mode import SAFE_MODE
from llm.seca.coach.chat_pipeline import (
    generate_chat_reply,
    ChatTurn as _ChatPipelineTurn,
)
from llm.seca.coach.live_move_pipeline import generate_live_reply
from llm.seca.storage.repo import (
    create_game,
    log_move,
    log_explanation,
    update_learning_score,
)

logger = logging.getLogger(__name__)
logger.info("Running server from: %s", __file__)
logger.info("SECA safe_mode=%s", SAFE_MODE)

load_dotenv()

API_KEY = os.getenv("SECA_API_KEY")
ENV = os.getenv("SECA_ENV", "dev")
IS_PROD = ENV in {"prod", "production"}
DEBUG = not IS_PROD

if IS_PROD and API_KEY is None:
    raise RuntimeError(
        "SECA_API_KEY env var is required in production (SECA_ENV=prod). "
        "Set a non-empty value before starting the server."
    )

app = FastAPI(title="SECA Chess Coach API")
app.state.limiter = limiter

# ---- CORS ----------------------------------------------------------------
_cors_origins = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
if not _cors_origins:
    logger.warning(
        "CORS_ALLOWED_ORIGINS is not set — all cross-origin requests will be blocked. "
        "Set CORS_ALLOWED_ORIGINS to a comma-separated list of allowed origins."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
)

# ---- Request body size limit (512 KB) ------------------------------------
_MAX_BODY_BYTES = 512 * 1024


class _LimitBodySize(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > _MAX_BODY_BYTES:
                    return JSONResponse(
                        status_code=413, content={"error": "Request body too large"}
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"error": "Invalid Content-Length"})
        return await call_next(request)


app.add_middleware(_LimitBodySize)


# ---- Security response headers -------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "Too many requests"})


DEFAULT_PREWARM_FENS = [
    chess.STARTING_FEN,
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",  # 1.e4 e5
    "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2",  # 1.d4 d5
    "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 2 3",
    "r2q1rk1/pp2bppp/2n1bn2/2pp4/3P4/2PBPN2/PP1N1PPP/R1BQ1RK1 w - - 0 9",
]


def verify_api_key(x_api_key: str = Header(None)):
    if API_KEY is None:
        if IS_PROD:
            raise HTTPException(status_code=500, detail="Server misconfiguration")
        return  # dev mode only — never allowed in prod
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


app.include_router(player_router)
app.include_router(auth_router)
app.include_router(game_router)
app.include_router(curriculum_router)
app.include_router(
    inference_router,
    prefix="/seca",
    tags=["seca-inference"],
    dependencies=[Depends(verify_api_key)],
)
tracker = ExplanationOutcomeTracker()
player_skill_memory: dict[str, SkillState] = {}
scheduler: CurriculumScheduler | None = None
event_storage: EventStore | None = None
skill_pipeline: SkillPipeline | None = None
world_model: SafeWorldModel | None = None
safe_explainer = SafeExplainer()

# ------------------------------------------------------------------
# Engine lifecycle
# ------------------------------------------------------------------

engine_pool: StockfishEnginePool | None = None
move_cache: FenMoveCache | None = None
move_stats = {"total": 0, "cache_hits": 0}
move_stats_lock = threading.Lock()
async_predict_enabled = True
async_predict_plies = 2
async_predict_movetime_ms = 20


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int_first(names: list[str], default: int) -> int:
    for name in names:
        raw = os.getenv(name)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return default


def _env_csv(name: str, default_csv: str) -> list[str]:
    raw = os.getenv(name, default_csv)
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def _normalize_fen(fen: str) -> str:
    if fen.strip().lower() == "startpos":
        return chess.STARTING_FEN
    return fen


def _cache_line_key(moves_uci: list[str] | None) -> str | None:
    if not moves_uci:
        return None
    return moves_uci[-1]


def _record_move_stat(cache_hit: bool) -> float:
    with move_stats_lock:
        move_stats["total"] += 1
        if cache_hit:
            move_stats["cache_hits"] += 1
        if move_stats["total"] == 0:
            return 0.0
        return move_stats["cache_hits"] / move_stats["total"]


def _env_fens(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return list(DEFAULT_PREWARM_FENS)
    return [_normalize_fen(part.strip()) for part in raw.split("||") if part.strip()]


@lru_cache(maxsize=4096)
def _fen_board(fen: str) -> chess.Board:
    return chess.Board(_normalize_fen(fen))


def _board_from_payload(fen: str, moves_uci: list[str] | None) -> chess.Board:
    normalized_fen = _normalize_fen(fen)
    board = _fen_board(normalized_fen).copy(stack=False)
    if not moves_uci:
        return board

    candidate = chess.Board()
    try:
        for move_uci in moves_uci:
            candidate.push_uci(move_uci)
        if candidate.fen() == normalized_fen:
            return candidate
    except ValueError:
        return board

    return board


def _predictive_cache_followups(
    *,
    seed_fen: str,
    mode: str,
    target_elo: int | None,
) -> None:
    if not async_predict_enabled or engine_pool is None or move_cache is None:
        return

    try:
        board = chess.Board(seed_fen)
    except ValueError:
        return

    line_key: str | None = None
    for _ in range(max(0, async_predict_plies)):
        if board.is_game_over():
            return

        cached = move_cache.get(
            fen=board.fen(),
            mode=mode,
            movetime_ms=async_predict_movetime_ms,
            target_elo=target_elo,
            line_key=line_key,
        )
        if cached:
            try:
                mv = chess.Move.from_uci(cached)
                if mv in board.legal_moves:
                    board.push(mv)
                    line_key = mv.uci()
                    continue
            except ValueError:
                pass

        try:
            mv = engine_pool.select_move(
                fen=board.fen(),
                board=board,
                mode=mode,
                movetime_ms=async_predict_movetime_ms,
                queue_timeout_ms=25,
                target_elo=target_elo,
            )
            move_cache.set(
                fen=board.fen(),
                mode=mode,
                movetime_ms=async_predict_movetime_ms,
                target_elo=target_elo,
                move_uci=mv.uci(),
                line_key=line_key,
            )
            board.push(mv)
            line_key = mv.uci()
        except Exception:
            return


@app.on_event("startup")
async def startup():
    global engine_pool, move_cache, scheduler, event_storage, skill_pipeline
    global world_model, async_predict_enabled, async_predict_plies, async_predict_movetime_ms
    try:
        init_db()
        world_model = SafeWorldModel()
        enforce(world_model)
        if os.name == "nt":
            default_stockfish_path = "engines/stockfish.exe"
        else:
            default_stockfish_path = shutil.which("stockfish") or "/usr/games/stockfish"
        stockfish_path = os.getenv("STOCKFISH_PATH", default_stockfish_path)
        settings = EnginePoolSettings(
            stockfish_path=stockfish_path,
            pool_size=max(1, _env_int("ENGINE_POOL_SIZE", 8)),
            threads=max(1, _env_int("ENGINE_THREADS", 1)),
            hash_mb=max(16, _env_int("ENGINE_HASH_MB", 128)),
            skill_level=_env_int("ENGINE_SKILL_LEVEL", 10),
            default_movetime_ms=max(20, _env_int("ENGINE_DEFAULT_MOVETIME_MS", 40)),
            training_movetime_ms=max(20, _env_int("ENGINE_TRAINING_MOVETIME_MS", 40)),
            analysis_movetime_ms=max(
                20,
                _env_int_first(
                    ["ENGINE_ANALYSIS_MOVETIME_MS", "ENGINE_DEEP_MOVETIME_MS"],
                    80,
                ),
            ),
            blitz_movetime_ms=max(20, _env_int("ENGINE_BLITZ_MOVETIME_MS", 25)),
            queue_timeout_ms=max(1, _env_int("ENGINE_QUEUE_TIMEOUT_MS", 50)),
        )
        engine_pool = StockfishEnginePool(settings)
        engine_pool.startup()
        move_cache = FenMoveCache(
            redis_url=os.getenv("REDIS_URL"),
            ttl_seconds=_env_int("MOVE_CACHE_TTL_SECONDS", 3600),
            max_memory_items=max(1, _env_int("MOVE_CACHE_L1_MAX_ITEMS", 500)),
        )
        async_predict_enabled = _env_bool("ENGINE_ASYNC_PREDICT_ENABLED", True)
        async_predict_plies = max(0, _env_int("ENGINE_ASYNC_PREDICT_PLIES", 2))
        async_predict_movetime_ms = max(
            20,
            _env_int("ENGINE_ASYNC_PREDICT_MOVETIME_MS", 20),
        )
        prewarm_fens = _env_fens("ENGINE_PREWARM_FENS")
        prewarm_modes = _env_csv("ENGINE_PREWARM_MODES", "blitz")
        if prewarm_fens and prewarm_modes:
            warmed = 0
            for mode in prewarm_modes:
                warmed += engine_pool.prewarm_cache(
                    move_cache=move_cache,
                    fens=prewarm_fens,
                    mode=mode,
                )
            logger.info(
                "Move cache prewarmed (entries=%d, positions=%d, modes=%s)",
                warmed,
                len(prewarm_fens),
                ",".join(prewarm_modes),
            )
        scheduler = CurriculumScheduler()
        logger.info("DB initialized")
        logger.info("Stockfish engine pool initialized (size=%d)", settings.pool_size)
    except Exception as e:
        if engine_pool:
            engine_pool.close()
        engine_pool = None
        move_cache = None
        logger.error("Stockfish engine pool DISABLED: %s", e)


@app.on_event("shutdown")
async def shutdown():
    if engine_pool:
        engine_pool.close()
        logger.info("Stockfish engine pool closed")


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

_VALID_MODES = {"default", "blitz", "analysis", "training"}


def _validate_fen_field(v: str) -> str:
    stripped = v.strip()
    if stripped.lower() == "startpos":
        return v
    parts = stripped.split()
    if len(parts) != 6 or len(stripped) > 100:
        raise ValueError("invalid FEN")
    return v


class MoveRequest(BaseModel):
    fen: str
    moves_uci: list[str] | None = None
    mode: str | None = "default"
    movetime_ms: int | None = None

    @field_validator("fen")
    @classmethod
    def validate_fen(cls, v: str) -> str:
        return _validate_fen_field(v)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str | None) -> str | None:
        if v is not None and v.lower() not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}")
        return v

    @field_validator("movetime_ms")
    @classmethod
    def validate_movetime(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 60_000):
            raise ValueError("movetime_ms must be 1–60000")
        return v


class AnalyzeRequest(BaseModel):
    fen: str
    stockfish_json: dict | None = None
    user_query: str | None = ""

    @field_validator("fen")
    @classmethod
    def validate_fen(cls, v: str) -> str:
        return _validate_fen_field(v)

    @field_validator("user_query")
    @classmethod
    def validate_user_query(cls, v: str | None) -> str | None:
        if v and len(v) > 2000:
            raise ValueError("user_query too long (max 2000 chars)")
        return sanitize_user_query(v) if v else v


class LiveMoveRequest(BaseModel):
    fen: str
    uci: str
    player_id: str = "demo"

    @field_validator("fen")
    @classmethod
    def validate_fen(cls, v: str) -> str:
        return _validate_fen_field(v)

    @field_validator("uci")
    @classmethod
    def validate_uci(cls, v: str) -> str:
        # UCI moves are 4–5 chars: source square (2) + target square (2) + optional promotion (1)
        if not (4 <= len(v) <= 5):
            raise ValueError("uci move must be 4–5 characters")
        return v

    @field_validator("player_id")
    @classmethod
    def validate_player_id(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError("player_id too long (max 100 chars)")
        return v


class StartGameRequest(BaseModel):
    player_id: str


class OutcomeRequest(BaseModel):
    explanation_id: str
    moves_analyzed: int
    avg_cpl: float
    blunder_rate: float
    tactic_success: bool
    confidence_delta: float

    @field_validator("explanation_id")
    @classmethod
    def validate_explanation_id(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("explanation_id too long (max 200 chars)")
        return v

    @field_validator("moves_analyzed")
    @classmethod
    def validate_moves_analyzed(cls, v: int) -> int:
        if not (0 <= v <= 10_000):
            raise ValueError("moves_analyzed must be 0–10000")
        return v

    @field_validator("avg_cpl")
    @classmethod
    def validate_avg_cpl(cls, v: float) -> float:
        if not (-3_000.0 <= v <= 3_000.0):
            raise ValueError("avg_cpl must be in [-3000, 3000]")
        return v

    @field_validator("blunder_rate")
    @classmethod
    def validate_blunder_rate(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("blunder_rate must be in [0.0, 1.0]")
        return v

    @field_validator("confidence_delta")
    @classmethod
    def validate_confidence_delta(cls, v: float) -> float:
        if not (-1.0 <= v <= 1.0):
            raise ValueError("confidence_delta must be in [-1.0, 1.0]")
        return v


class CurriculumRecommendRequest(BaseModel):
    skill_vector: list[float]


class GameRequest(BaseModel):
    player_id: str
    pgn: str


class GameFinishRequest(BaseModel):
    player_id: str
    pgn: str


class GameFinishClosedLoopRequest(BaseModel):
    player_id: int
    game_id: int


class ChatTurnModel(BaseModel):
    """A single turn in a coaching conversation."""

    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if len(v) > 2000:
            raise ValueError("message content too long (max 2000 chars)")
        return sanitize_user_query(v) if v else v


class ChatRequest(BaseModel):
    """Request body for POST /chat."""

    fen: str
    messages: list[ChatTurnModel]
    player_profile: dict | None = None
    past_mistakes: list[str] | None = None
    move_count: int | None = None

    @field_validator("fen")
    @classmethod
    def validate_fen(cls, v: str) -> str:
        return _validate_fen_field(v)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v: list) -> list:
        if len(v) > 50:
            raise ValueError("too many messages in history (max 50)")
        return v

    @field_validator("past_mistakes")
    @classmethod
    def validate_past_mistakes(cls, v: list | None) -> list | None:
        if v is not None and len(v) > 20:
            raise ValueError("past_mistakes list too long (max 20)")
        return v

    @field_validator("move_count")
    @classmethod
    def validate_move_count(cls, v: int | None) -> int | None:
        if v is not None and not (0 <= v <= 10_000):
            raise ValueError("move_count must be 0–10000")
        return v


def build_engine_signal(req: AnalyzeRequest):
    return extract_engine_signal(req.stockfish_json, fen=req.fen)


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/seca/status")
def seca_status():
    """Return SECA runtime safety flags.

    Open endpoint (no auth): readable by Android at cold-start so the client
    can confirm safe_mode is active before sending any coaching requests.
    Always ``safe_mode: true`` in the current release; bandit training and
    neural policy updates are hard-disabled via SAFE_MODE = True in
    ``llm/seca/runtime/safe_mode.py``.
    """
    return {
        "safe_mode": SAFE_MODE,
        "bandit_enabled": not SAFE_MODE,
        "version": "1.0",
    }


@app.get("/debug/engine")
def engine_debug(_: None = Depends(verify_api_key)):
    if engine_pool is None:
        return {"pool_size": 0}
    return {"pool_size": engine_pool.qsize()}


# ------------------------------------------------------------------
# Move endpoint (pooled stockfish)
# ------------------------------------------------------------------


@app.post("/move")
@limiter.limit("30/minute")
def move(
    req: MoveRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    player=Depends(get_current_player),
):
    request_started = time.perf_counter()
    if engine_pool is None:
        return {"error": "engine pool unavailable"}

    normalized_fen = _normalize_fen(req.fen)
    board = _board_from_payload(normalized_fen, req.moves_uci)
    adaptation = compute_adaptation(player.rating, player.confidence)
    target_elo = adaptation["opponent"]["target_elo"]

    mode = (req.mode or "default").lower()
    resolved_movetime_ms = engine_pool.resolve_movetime_ms(mode, req.movetime_ms)
    line_key = _cache_line_key(req.moves_uci)

    cache_hit = False
    fallback_used = False
    engine_time_ms = 0.0
    mv: chess.Move | None = None

    if move_cache:
        cached_uci = move_cache.get(
            fen=normalized_fen,
            mode=mode,
            movetime_ms=resolved_movetime_ms,
            target_elo=target_elo,
            line_key=line_key,
        )
        if cached_uci:
            try:
                candidate = chess.Move.from_uci(cached_uci)
                if candidate in board.legal_moves:
                    mv = candidate
                    cache_hit = True
            except ValueError:
                mv = None

    if cache_hit and mv is not None:
        san = board.san(mv)
        cache_hit_rate = _record_move_stat(cache_hit=True)
        latency_ms = round((time.perf_counter() - request_started) * 1000.0, 2)
        return {
            "uci": mv.uci(),
            "san": san,
            "opponent_elo": target_elo,
            "mode": mode,
            "movetime_ms": resolved_movetime_ms,
            "cache_hit": True,
            "fallback_used": False,
            "telemetry": {
                "latency_ms": latency_ms,
                "engine_time_ms": 0.0,
                "cache_hit_rate": round(cache_hit_rate, 4),
                "queue_depth": engine_pool.qsize(),
            },
        }

    try:
        engine_started = time.perf_counter()
        mv = engine_pool.select_move(
            fen=normalized_fen,
            board=board,
            moves_uci=req.moves_uci,
            mode=mode,
            movetime_ms=resolved_movetime_ms,
            target_elo=target_elo,
        )
        engine_time_ms = round((time.perf_counter() - engine_started) * 1000.0, 2)
    except RuntimeError:
        mv = engine_pool.fast_fallback_move(board)
        fallback_used = True
        engine_time_ms = round((time.perf_counter() - request_started) * 1000.0, 2)

    if move_cache and not fallback_used:
        move_cache.set(
            fen=normalized_fen,
            mode=mode,
            movetime_ms=resolved_movetime_ms,
            target_elo=target_elo,
            move_uci=mv.uci(),
            line_key=line_key,
        )

    san = board.san(mv)
    ply = board.fullmove_number * 2 - (0 if board.turn else 1)
    log_move(
        game_id="demo",  # temporary until session system
        ply=ply,
        fen=normalized_fen,
        uci=mv.uci(),
        san=san,
        eval=None,
    )
    board_after = board.copy(stack=False)
    board_after.push(mv)
    if async_predict_enabled and not fallback_used:
        background_tasks.add_task(
            _predictive_cache_followups,
            seed_fen=board_after.fen(),
            mode=mode,
            target_elo=target_elo,
        )
    cache_hit_rate = _record_move_stat(cache_hit=cache_hit)
    latency_ms = round((time.perf_counter() - request_started) * 1000.0, 2)

    return {
        "uci": mv.uci(),
        "san": san,
        "opponent_elo": target_elo,
        "mode": mode,
        "movetime_ms": resolved_movetime_ms,
        "cache_hit": cache_hit,
        "fallback_used": fallback_used,
        "telemetry": {
            "latency_ms": latency_ms,
            "engine_time_ms": engine_time_ms,
            "cache_hit_rate": round(cache_hit_rate, 4),
            "queue_depth": engine_pool.qsize(),
        },
    }


# ------------------------------------------------------------------
# Live move endpoint (realtime coaching)
# ------------------------------------------------------------------


@app.post("/live/move")
@limiter.limit("30/minute")
def live_move(
    req: LiveMoveRequest,
    request: Request,
    player=Depends(get_current_player),
):
    adaptation = compute_adaptation(player.rating, player.confidence)
    result = generate_live_reply(
        fen=req.fen,
        uci=req.uci,
        player_id=str(player.id),
        explanation_style=adaptation["teaching"]["style"],
    )
    return {
        "status": "ok",
        "hint": result.hint,
        "engine_signal": result.engine_signal,
        "move_quality": result.move_quality,
        "mode": result.mode,
    }


# ------------------------------------------------------------------
# Analyze endpoint (engine signal only)
# ------------------------------------------------------------------


@app.post("/analyze")
@limiter.limit("30/minute")
def analyze(req: AnalyzeRequest, request: Request, _: None = Depends(verify_api_key)):
    return {"engine_signal": build_engine_signal(req)}


@app.get("/next-training/{player_id}")
def next_training(player_id: str, _: str = Depends(verify_api_key)):
    skill = player_skill_memory.get(player_id, SkillState())

    # demo weaknesses (later from analyzer)
    weaknesses = [
        Weakness("tactics", severity=0.7, confidence=0.9),
        Weakness("endgame", severity=0.4, confidence=0.8),
    ]

    task = scheduler.next_task(weaknesses, skill.rating)

    return {
        "topic": task.topic,
        "difficulty": task.difficulty,
        "format": task.format,
        "expected_gain": task.expected_gain,
    }


@app.post("/game/start")
def start_game(req: StartGameRequest, _: str = Depends(verify_api_key)):
    game_id = create_game(req.player_id)
    return {"game_id": game_id}


# ------------------------------------------------------------------
# Explain endpoint (LLM layer comes next)
# ------------------------------------------------------------------


@app.post("/explain")
def explain(req: AnalyzeRequest, _: str = Depends(verify_api_key)):
    engine_signal = extract_engine_signal(req.stockfish_json, fen=req.fen)
    explanation = safe_explainer.explain(engine_signal)

    response = {
        "explanation": explanation,
        "engine_signal": engine_signal,
        "mode": "SAFE_V1",
    }
    validate_explain_response(response)
    return response


@app.post("/explanation_outcome")
@limiter.limit("20/minute")
def report_outcome(req: OutcomeRequest, request: Request, _: None = Depends(verify_api_key)):
    tracker.record_outcome(**req.dict())

    score = tracker.compute_learning_score(req.explanation_id)

    return {"learning_score": score}


# ------------------------------------------------------------------
# Chat endpoint (long-form coaching conversation)
# ------------------------------------------------------------------


@app.post("/chat")
@limiter.limit("10/minute")
def chat(
    req: ChatRequest,
    request: Request,
    _: str = Depends(verify_api_key),
):
    """Long-form coaching conversation endpoint.

    Accepts the current FEN, full conversation history, and optional
    player context.  Returns a deterministic coaching reply that always
    references the engine evaluation.  No RL adaptation occurs.
    """
    turns = [_ChatPipelineTurn(role=t.role, content=t.content) for t in req.messages]
    result = generate_chat_reply(
        fen=req.fen,
        messages=turns,
        player_profile=req.player_profile,
        past_mistakes=req.past_mistakes,
        move_count=req.move_count,
    )
    return {
        "reply": result.reply,
        "engine_signal": result.engine_signal,
        "mode": result.mode,
    }
