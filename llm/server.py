import chess
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from .player_api import router as player_router
from llm.seca.auth.router import router as auth_router
from llm.seca.events.router import router as game_router
from llm.seca.curriculum.router import router as curriculum_router
# register SECA models
import llm.seca.events.models

from llm.seca.engines.adaptive.controller import AdaptiveOpponent
from llm.rag.engine_signal.extract_engine_signal import extract_engine_signal
from llm.explain_pipeline import generate_validated_explanation
from llm.seca.learning.outcome_tracker import ExplanationOutcomeTracker
from llm.seca.learning.pipeline import run_skill_update
from llm.seca.learning.skill_update import SkillState
from llm.seca.adaptation.coupling import compute_adaptation
from llm.seca.curriculum.scheduler import CurriculumScheduler
from llm.seca.curriculum.types import Weakness
from llm.seca.storage.db import init_db
from llm.seca.storage.event_store import EventStore
from llm.seca.skill.pipeline import SkillPipeline
from llm.seca.world_model.safe_stub import SafeWorldModel
from llm.seca.explainer.safe_explainer import SafeExplainer
from llm.seca.storage.repo import (
    create_game,
    finish_game,
    log_move,
    log_explanation,
    update_learning_score,
)

print(">>> RUNNING SERVER FROM:", __file__)

app = FastAPI(title="SECA Chess Coach API")
app.include_router(player_router)
app.include_router(auth_router)
app.include_router(game_router)
app.include_router(curriculum_router)
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

opponent: AdaptiveOpponent | None = None
engine_lock = asyncio.Lock()


@app.on_event("startup")
async def startup():
    global opponent, scheduler, event_storage, skill_pipeline
    global world_model
    try:
        init_db()  # ← NEW
        world_model = SafeWorldModel()
        opponent = AdaptiveOpponent(
            stockfish_path=r"C:\Users\artgu\chesscoach\stockfish.exe",
            target_elo=1600,
        )
        scheduler = CurriculumScheduler()
        print(">>> DB initialized")
        print(">>> AdaptiveOpponent initialized")
    except Exception as e:
        opponent = None
        print(">>> AdaptiveOpponent DISABLED:", e)


@app.on_event("shutdown")
async def shutdown():
    if opponent:
        opponent.sf.close()
        print(">>> Stockfish closed")


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class MoveRequest(BaseModel):
    fen: str


class AnalyzeRequest(BaseModel):
    fen: str
    stockfish_json: dict | None = None
    user_query: str | None = ""


class LiveMoveRequest(BaseModel):
    fen: str
    uci: str
    player_id: str = "demo"


class StartGameRequest(BaseModel):
    player_id: str


class OutcomeRequest(BaseModel):
    explanation_id: str
    moves_analyzed: int
    avg_cpl: float
    blunder_rate: float
    tactic_success: bool
    confidence_delta: float


class FinishGameRequest(BaseModel):
    game_id: str
    player_id: str
    result: str  # win/loss/draw


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


def build_engine_signal(req: AnalyzeRequest):
    return extract_engine_signal(req.stockfish_json, fen=req.fen)


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}

# ------------------------------------------------------------------
# Move endpoint (adaptive opponent)
# ------------------------------------------------------------------

@app.post("/move")
async def move(req: MoveRequest):
    if opponent is None:
        return {"error": "adaptive opponent unavailable"}

    async with engine_lock:
        board = chess.Board(req.fen)
        # demo player
        skill = player_skill_memory.get("demo", SkillState())
        adaptation = compute_adaptation(skill.rating, skill.confidence)

        opponent.configure(adaptation["opponent"])

        mv = opponent.select_move(board)
        ply = board.fullmove_number * 2 - (0 if board.turn else 1)
        log_move(
            game_id="demo",   # temporary until session system
            ply=ply,
            fen=req.fen,
            uci=mv.uci(),
            san=board.san(mv),
            eval=None,
        )

        return {
            "uci": mv.uci(),
            "san": board.san(mv),
            "opponent_elo": adaptation["opponent"]["target_elo"],
        }


# ------------------------------------------------------------------
# Live move endpoint (realtime coaching)
# ------------------------------------------------------------------

@app.post("/live/move")
def live_move(req: LiveMoveRequest):
    # TODO: wire LiveCoach and realtime analyzer pipeline
    return {
        "status": "not_implemented",
        "message": "Live coaching pipeline not wired yet.",
    }


# ------------------------------------------------------------------
# Analyze endpoint (engine signal only)
# ------------------------------------------------------------------

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    return {"engine_signal": build_engine_signal(req)}


@app.get("/next-training/{player_id}")
def next_training(player_id: str):
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
def start_game(req: StartGameRequest):
    game_id = create_game(req.player_id)
    return {"game_id": game_id}


@app.post("/game/finish")
def finish_game_endpoint(req: FinishGameRequest):
    finish_game(req.game_id, req.result)

    # demo placeholders until full analyzer wired
    moves = []
    explanations = []

    skill = player_skill_memory.get(req.player_id, SkillState())

    new_skill = run_skill_update(skill, moves, req.result, explanations)

    player_skill_memory[req.player_id] = new_skill

    return {
        "new_rating": new_skill.rating,
        "confidence": new_skill.confidence,
    }


# ------------------------------------------------------------------
# Explain endpoint (LLM layer comes next)
# ------------------------------------------------------------------

@app.post("/explain")
def explain(req: AnalyzeRequest):
    engine_signal = extract_engine_signal(req.stockfish_json, fen=req.fen)
    explanation = safe_explainer.explain(engine_signal)

    return {
        "explanation": explanation,
        "engine_signal": engine_signal,
        "mode": "SAFE_V1",
    }


@app.post("/explanation_outcome")
def report_outcome(req: OutcomeRequest):
    tracker.record_outcome(**req.dict())

    score = tracker.compute_learning_score(req.explanation_id)

    return {"learning_score": score}


