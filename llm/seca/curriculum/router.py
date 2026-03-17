import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from llm.seca.auth.router import get_db, get_current_player
from .generator import CurriculumGenerator

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


@router.post("/next")
def next_training(
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
