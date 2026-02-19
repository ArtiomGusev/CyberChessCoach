from fastapi import APIRouter, Depends, Request
import json
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from llm.seca.auth.router import get_db, get_current_player
from .storage import EventStorage
from llm.seca.skills.updater import SkillUpdater
from llm.seca.brain.bandit.online_update import update_after_game
from llm.seca.brain.bandit.context_builder import build_context_vector
from llm.seca.brain.models import RatingUpdate, ConfidenceUpdate
from llm.seca.coach.live_controller import (
    PostGameCoachController,
    GameSummary,
)
from llm.seca.events.models import GameEvent
from llm.seca.coach.executor import CoachExecutor
from types import SimpleNamespace

router = APIRouter(prefix="/game", tags=["game"])


class GameFinishRequest(BaseModel):
    pgn: str
    result: str        # win / loss / draw
    accuracy: float    # 0..1
    weaknesses: dict


@router.post("/finish")
def finish_game(
    req: GameFinishRequest,
    player=Depends(get_current_player),
    request: Request = None,
    db: DBSession = Depends(get_db),
):
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
    SkillUpdater(db).update_from_event(player.id, event)
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

    context = build_context_vector(
        rating_before=rating_before,
        confidence_before=confidence_before,
        accuracy=req.accuracy,
        weaknesses=req.weaknesses,
    )

    try:
        update_after_game(context, action_index=0, reward=reward)
        from llm.seca.brain.bandit.trainer import train_bandit
        from llm.seca.brain.neural_policy.train import train_policy
        train_bandit()
        train_policy()
    except Exception:
        import traceback
        print("\n=== BANDIT UPDATE ERROR ===")
        traceback.print_exc()
        print("=== END BANDIT ERROR ===\n")

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
        import traceback
        print("\n=== COUNTERFACTUAL ERROR ===")
        traceback.print_exc()
        print("=== END COUNTERFACTUAL ERROR ===\n")

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
        import traceback
        print("\n=== COACH PIPELINE ERROR ===")
        traceback.print_exc()
        print("=== END COACH ERROR ===\n")
        coach_action = SimpleNamespace(type="default", weakness=None, reason="fallback")
        coach_content = SimpleNamespace(
            title="Keep playing",
            description="No special training needed right now.",
            payload={},
        )


    learner = request.app.state.seca_learner if request else None
    try:
        learning_result = learner.train_step() if learner else {"status": "no_learner"}
    except Exception:
        import traceback
        print("\n=== LEARNER ERROR ===")
        traceback.print_exc()
        print("=== END LEARNER ERROR ===\n")
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
