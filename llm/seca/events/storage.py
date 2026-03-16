import json
from sqlalchemy.orm import Session as DBSession

from .models import GameEvent
from ..analytics.logger import AnalyticsLogger
from ..analytics.events import EventType


class EventStorage:
    def __init__(self, db: DBSession):
        self.db = db

    # -------------------------
    # Store finished game
    # -------------------------
    def store_game(
        self,
        player_id: str,
        pgn: str,
        result: str,
        accuracy: float,
        weaknesses: dict,
    ) -> GameEvent:

        event = GameEvent(
            player_id=player_id,
            pgn=pgn,
            result=result,
            accuracy=accuracy,
            weaknesses_json=json.dumps(weaknesses),
        )

        self.db.add(event)
        try:
            # === rating & confidence update logic ===
            # rating_update = ...
            # confidence_update = ...
            #
            # self.db.add(rating_update)
            # self.db.add(confidence_update)
            self.db.commit()
        except Exception as e:
            import traceback
            print("\n=== LEARNING PIPELINE CRASH ===")
            traceback.print_exc()
            print("=== END CRASH ===\n")
            raise
        self.db.refresh(event)

        AnalyticsLogger(self.db).log(
            event_type=EventType.GAME_FINISHED,
            player_id=str(player_id),
            payload={
                "result": result,
                "accuracy": accuracy,
                "weaknesses": weaknesses,
            },
        )

        return event

    # -------------------------
    # Load recent events
    # -------------------------
    def get_recent_games(self, player_id: str, limit: int = 20):
        """Return the most recent GameEvent records for a specific player."""
        return (
            self.db.query(GameEvent)
            .filter_by(player_id=player_id)
            .order_by(GameEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_all_recent_games(self, limit: int = 50):
        """Return the most recent GameEvent records across all players."""
        return (
            self.db.query(GameEvent)
            .order_by(GameEvent.created_at.desc())
            .limit(limit)
            .all()
        )

