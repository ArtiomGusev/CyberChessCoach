import io
import json
import logging
import re

import chess.pgn

_PGN_HEADER_RE = re.compile(r'^\s*\[\s*\w+\s+"[^"]*"\s*\]', re.MULTILINE)
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session as DBSession

from llm.seca.auth.router import get_db, get_current_player
from .storage import EventStorage
from llm.seca.skills.updater import SkillUpdater
from llm.seca.brain.models import RatingUpdate, ConfidenceUpdate
from llm.seca.coach.live_controller import (
    PostGameCoachController,
    GameSummary,
)
from llm.seca.events.models import GameEvent
from llm.seca.coach.executor import CoachExecutor
from types import SimpleNamespace
from llm.seca.runtime.safe_mode import SAFE_MODE

router = APIRouter(prefix="/game", tags=["game"])


class GameFinishRequest(BaseModel):
    pgn: str
    result: str  # win / loss / draw
    accuracy: float  # 0..1
    weaknesses: dict
    player_id: str | None = None

    @field_validator("pgn")
    @classmethod
    def validate_pgn(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("pgn must not be empty")
        if len(v) > 100_000:
            raise ValueError("pgn too large (max 100 000 chars)")
        if not _PGN_HEADER_RE.search(v):
            raise ValueError("invalid PGN: no PGN headers found")
        try:
            game = chess.pgn.read_game(io.StringIO(v))
        except Exception as exc:
            raise ValueError(f"invalid PGN: {exc}") from exc
        if game is None:
            raise ValueError("invalid PGN: no game found")
        if game.errors:
            raise ValueError(f"invalid PGN: {game.errors[0]}")
        return v

    @field_validator("result")
    @classmethod
    def validate_result(cls, v: str) -> str:
        if v not in {"win", "loss", "draw"}:
            raise ValueError("result must be 'win', 'loss', or 'draw'")
        return v

    @field_validator("accuracy")
    @classmethod
    def validate_accuracy(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("accuracy must be between 0.0 and 1.0")
        return v

    @field_validator("weaknesses")
    @classmethod
    def validate_weaknesses(cls, v: dict) -> dict:
        if len(v) > 50:
            raise ValueError("too many weakness entries (max 50)")
        for k, val in v.items():
            if not isinstance(k, str) or len(k) > 100:
                raise ValueError("weakness key must be a string ≤ 100 chars")
            if not isinstance(val, (int, float)):
                raise ValueError("weakness values must be numeric")
        return v


@router.post("/finish")
def finish_game(
    req: GameFinishRequest,
    player=Depends(get_current_player),
    request: Request = None,
    db: DBSession = Depends(get_db),
):
    if req.player_id is not None and req.player_id != str(player.id):
        raise HTTPException(status_code=403, detail="Cannot submit game for another player")

    storage = EventStorage(db)

    rating_before = player.rating
    confidence_before = player.confidence

    event = storage.store_game(
        player_id=player.id,
        pgn=req.pgn,
        result=req.result,
        accuracy=req.accuracy,
        weaknesses=req.weaknesses,
    )

    # ---- skill update ----
    try:
        SkillUpdater(db).update_from_event(player.id, event)
    except Exception:
        logger.exception(
            "SkillUpdater failed for player %s; rating not updated this game", player.id
        )
    db.refresh(player)

    rating_after = player.rating
    confidence_after = player.confidence
    reward = rating_after - rating_before
    rating_update = RatingUpdate(
        event_id=str(event.id),
        rating_before=float(rating_before),
        rating_after=float(rating_after),
    )
    confidence_update = ConfidenceUpdate(
        event_id=str(event.id),
        confidence_before=float(confidence_before),
        confidence_after=float(confidence_after),
    )
    db.add(rating_update)
    db.add(confidence_update)
    db.commit()

    if not SAFE_MODE:
        from llm.seca.brain.bandit.context_builder import build_context_vector

        context = build_context_vector(
            rating_before=rating_before,
            confidence_before=confidence_before,
            accuracy=req.accuracy,
            weaknesses=req.weaknesses,
        )

        try:
            from llm.seca.brain.bandit.online_update import update_after_game

            update_after_game(context, action_index=0, reward=reward)
            from llm.seca.brain.bandit.trainer import train_bandit
            from llm.seca.brain.neural_policy.train import train_policy

            train_bandit()
            train_policy()
        except Exception:
            logger.exception("Bandit update failed")

        try:
            from llm.seca.brain.planning.counterfactual import CounterfactualPlanner
            import numpy as np

            planner = CounterfactualPlanner()

            state = np.array([rating_after, confidence_after, req.accuracy])

            actions = [
                np.array([1, 0, 0]),  # tactics
                np.array([0, 1, 0]),  # openings
                np.array([0, 0, 1]),  # endgames
            ]

            idx, future, score = planner.choose_action(state, actions)

            print("Chosen training:", idx)
            print("Predicted rating/conf delta:", future)
            print("Score:", score)
        except Exception:
            logger.exception("Counterfactual planner failed")

    controller = PostGameCoachController()

    game_summary = GameSummary(
        rating_before=rating_before,
        rating_after=rating_after,
        confidence_before=confidence_before,
        confidence_after=confidence_after,
        learning_delta=reward,
        weaknesses=req.weaknesses or {},
    )

    recent = (
        db.query(GameEvent)
        .filter(GameEvent.player_id == player.id)
        .order_by(GameEvent.created_at.desc())
        .limit(3)
        .all()
    )

    recent_weaknesses = []
    for ev in recent:
        if not ev.weaknesses_json:
            continue
        try:
            weaknesses = json.loads(ev.weaknesses_json)
            if isinstance(weaknesses, dict):
                recent_weaknesses.extend(list(weaknesses.keys()))
        except Exception:
            # Ignore malformed weakness payloads
            pass

    try:
        coach_action = controller.decide(
            game=game_summary,
            recent_weaknesses=recent_weaknesses,
        )

        executor = CoachExecutor()
        coach_content = executor.execute(coach_action)
    except Exception:
        logger.exception("Coach pipeline failed")
        coach_action = SimpleNamespace(type="ERROR", weakness=None, reason="coach_pipeline_error")
        coach_content = SimpleNamespace(
            title="Keep playing",
            description="No special training needed right now.",
            payload={},
        )

    if SAFE_MODE:
        learning_result = {"status": "safe_mode"}
    else:
        learner = request.app.state.seca_learner if request else None
        try:
            learning_result = learner.train_step() if learner else {"status": "no_learner"}
        except Exception:
            logger.exception("Learner train_step failed")
            learning_result = {"status": "learner_error"}

    return {
        "status": "stored",
        "new_rating": rating_after,
        "confidence": confidence_after,
        "learning": learning_result,
        "coach_action": {
            "type": coach_action.type,
            "weakness": coach_action.weakness,
            "reason": coach_action.reason,
        },
        "coach_content": {
            "title": coach_content.title,
            "description": coach_content.description,
            "payload": coach_content.payload,
        },
    }
