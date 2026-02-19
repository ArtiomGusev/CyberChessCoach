import json
from sqlalchemy.orm import Session as DBSession

from llm.seca.auth.models import Player
from llm.seca.events.storage import EventStorage
from .models import TrainingPlan
from .policy import CurriculumPolicy


class CurriculumGenerator:

    def __init__(self, db: DBSession):
        self.db = db
        self.policy = CurriculumPolicy()
        self.events = EventStorage(db)

    # ------------------------------------------------

    def generate(self, player_id: str) -> TrainingPlan:

        player = self.db.query(Player).filter_by(id=player_id).first()
        if not player:
            raise ValueError("Player not found")

        skill_vector = json.loads(player.skill_vector_json or "{}")

        topic = self.policy.choose_topic(skill_vector)
        difficulty = self.policy.choose_difficulty(player.rating, player.confidence)
        exercise_type = self.policy.choose_exercise_type(topic)
        session_length = self.policy.choose_session_length(player.confidence)

        payload = {
            "session_minutes": session_length,
            "focus": topic,
            "difficulty": difficulty,
            "exercise": exercise_type,
        }

        plan = TrainingPlan(
            player_id=player_id,
            topic=topic,
            difficulty=difficulty,
            exercise_type=exercise_type,
            payload_json=json.dumps(payload),
        )

        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)

        return plan
