import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from llm.seca.auth.models import Base, Player


class GameEvent(Base):
    __tablename__ = "game_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    player_id: Mapped[str | None] = mapped_column(String, ForeignKey("players.id"), index=True)

    # raw PGN or compact move list
    pgn: Mapped[str] = mapped_column(Text, nullable=False)

    # result: win / loss / draw
    result: Mapped[str] = mapped_column(String, nullable=False)

    # engine accuracy / centipawn loss etc.
    accuracy: Mapped[float | None] = mapped_column(Float, default=0.0)

    # detected weaknesses JSON
    weaknesses_json: Mapped[str | None] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship("Player")
