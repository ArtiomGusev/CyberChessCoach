"""SQLAlchemy declarative models for the storage tables that used to
live in raw-sqlite3 land (``schema.sql``).

Background
----------
Until 2026-05-09, ``games`` / ``moves`` / ``explanations`` /
``repertoire`` / ``bandit_weights`` were created by ``schema.sql`` and
written/read via raw ``sqlite3`` (with ``?`` placeholders against a
hardcoded ``data/seca.db``).  Auth tables (``players`` etc.) lived in
SQLAlchemy and could be backed by Postgres in production via
``DATABASE_URL``.

The two paths drifted into different physical databases under
production: in Postgres deployments the auth tables landed in Postgres
while the games tables stayed in a SQLite file, and the ``games.player_id
→ players.id`` foreign key couldn't be satisfied — ``/game/start``
returned 500 with ``sqlite3.IntegrityError: FOREIGN KEY constraint
failed``.

The fix unifies ownership: every table is modelled here in SQLAlchemy
and created by ``init_schema()`` against whatever ``DATABASE_URL``
points at.  ``schema.sql`` is gone; ``repo.py`` now talks to
``SessionLocal`` rather than raw ``sqlite3``.  See the PR notes for the
manual data-migration story (out of scope for the code change).

Column types are dialect-portable: ``Integer`` PKs become ``SERIAL`` on
Postgres and ``INTEGER PRIMARY KEY AUTOINCREMENT`` on SQLite via
SQLAlchemy's autoincrement handling.  ``DateTime(timezone=False)`` is
used for timestamp columns to mirror the prior ``CURRENT_TIMESTAMP``
naive-UTC behaviour without forcing a timezone migration.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from llm.seca.auth.models import Base


class Game(Base):
    """One row per ``/game/start`` (or per ``get_or_create_auto_game``
    for auto-grouped move logging).

    The PK is a TEXT (UUID for explicit ``/game/start`` calls,
    ``"auto-{player_id}"`` for the deterministic auto-game key) — kept
    as ``String`` to preserve the prior contract; callers send these IDs
    around and the Android client persists them in SharedPreferences,
    so changing the type would force a coordinated client+server
    release.

    Checkpoint columns (``current_fen`` / ``current_uci_history`` /
    ``last_checkpoint_at``) are populated by ``checkpoint_game()`` for
    cross-device resume; ``GET /game/active`` filters on
    ``finished_at IS NULL AND current_fen IS NOT NULL``.
    """

    __tablename__ = "games"

    id = Column(String, primary_key=True)
    player_id = Column(String, ForeignKey("players.id"), index=True)
    result = Column(String)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)

    # In-progress checkpoint state for cross-device resume.
    current_fen = Column(Text)
    current_uci_history = Column(Text)
    last_checkpoint_at = Column(DateTime)


class Move(Base):
    """One row per ply logged via ``log_move()``.

    Surrogate integer PK (was ``INTEGER PRIMARY KEY AUTOINCREMENT`` in
    schema.sql) — SQLAlchemy maps this to ``SERIAL`` on Postgres
    automatically.
    """

    __tablename__ = "moves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey("games.id"), index=True)
    ply = Column(Integer)
    fen = Column(Text)
    uci = Column(String)
    san = Column(String)
    # ``eval`` shadows a Python builtin; column name is preserved (the
    # raw-sqlite schema used it) — the Python attribute on the model is
    # the same since SQLAlchemy column attributes are namespaced inside
    # the model class.
    eval = Column(Float)


class Explanation(Base):
    """One row per explanation served, tracked for the
    ``/explanation_outcome`` learning-score loop."""

    __tablename__ = "explanations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey("games.id"), index=True)
    ply = Column(Integer)
    explanation_type = Column(String)
    confidence = Column(Float)
    learning_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class BanditWeights(Base):
    """LinUCB sufficient statistics for one (player, action) pair.

    See ``llm/seca/brain/bandit/decision.py`` for the math.  Stored as
    JSON-encoded matrices (``A_json``) and vectors (``b_json``) so the
    table stays portable across SQLite and Postgres without depending
    on numpy-aware column types.
    """

    __tablename__ = "bandit_weights"
    __table_args__ = (
        UniqueConstraint("player_id", "action", name="uq_bandit_weights_player_action"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    n_features = Column(Integer, nullable=False)
    A_json = Column(Text, nullable=False)
    b_json = Column(Text, nullable=False)
    alpha = Column(Float, nullable=False, default=1.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Repertoire(Base):
    """One opening line per row, scoped to a player.

    ``is_active`` is stored as an Integer (0/1) rather than Boolean so
    the column shape matches the prior raw-sqlite schema and avoids a
    SQLite/Postgres BOOL <-> INT migration headache.  Callers that
    serialise to JSON convert via ``bool(row.is_active)``; that
    conversion already lived in ``list_repertoire()`` pre-migration so
    the API contract is preserved.
    """

    __tablename__ = "repertoire"
    __table_args__ = (UniqueConstraint("player_id", "eco", name="uq_repertoire_player_eco"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, ForeignKey("players.id"), nullable=False, index=True)
    eco = Column(String, nullable=False)
    name = Column(String, nullable=False)
    line = Column(String, nullable=False)
    mastery = Column(Float, nullable=False, default=0.0)
    is_active = Column(Integer, nullable=False, default=0)
    ordinal = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


__all__ = [
    "Game",
    "Move",
    "Explanation",
    "BanditWeights",
    "Repertoire",
]
