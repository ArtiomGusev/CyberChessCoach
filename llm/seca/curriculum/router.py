import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DBSession

from llm.seca.auth.router import get_db, get_current_player
from llm.seca.shared_limiter import limiter
from .generator import CurriculumGenerator

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


@router.post("/next")
@limiter.limit("20/minute")
def next_training(
    request: Request,
    player=Depends(get_current_player),
    db: DBSession = Depends(get_db),
):
    plan = CurriculumGenerator(db).generate(player.id)

    return {
        "topic": plan.topic,
        "difficulty": plan.difficulty,
        "exercise_type": plan.exercise_type,
        "payload": json.loads(plan.payload_json),
    }
