"""
Weekly coaching digest — deterministic agent-style intervention.

Produces a small structured digest summarising the three most prominent
weakness categories from the trailing ``window_days`` of play and pairs
each with a single targeted microtask. The digest is engine-grounded:
inputs are the per-game weakness vectors already computed at finish-time
by ``GameWeaknessAnalyzer`` and stored on ``GameEvent.weaknesses_json``.
No LLM is invoked here, no Stockfish re-evaluation runs, no model
inference happens — selection and prose come from a fixed rule table so
the output is reproducible from the stored game history alone.

Public API
----------
``build_weekly_digest(db, player_id, *, now=None, window_days=7)``
    Pure builder. Reads recent games, aggregates, selects top categories,
    emits microtasks. Returns a plain dict ready for JSON serialisation
    or persistence — does NOT touch the digests table.

``persist_weekly_digest(db, player_id, digest)``
    Persists a builder output as a new ``WeeklyDigest`` row and commits.

``get_latest_digest(db, player_id)``
    Returns the most recently generated ``WeeklyDigest`` for the player,
    or ``None`` if none exists.

Selection rule
--------------
The 3 holes are the 3 categories with the highest ``category_scores``
value among the in-window games, excluding zero-scored categories.
Ties are broken alphabetically by category name so the ordering is
deterministic across runs and dialects.

This is intentionally different from
``generate_training_recommendations`` in the same package, which gates
emission on per-category thresholds and is used by the always-on
progress view. The digest wants exactly the *biggest* holes in the
recent window, not the categories that crossed an absolute threshold.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session as DBSession

from llm.seca.analytics.mistake_stats import (
    MistakeCategory,
    aggregate_from_weakness_dicts,
)
from llm.seca.analytics.models import WeeklyDigest
from llm.seca.analysis.historical_pipeline import HistoricalAnalysisPipeline
from llm.seca.events.models import GameEvent

DEFAULT_WINDOW_DAYS = 7
MAX_HOLES = 3


_HOLE_TITLES: dict[str, str] = {
    MistakeCategory.OPENING_PREPARATION: "Errors concentrated in the opening phase",
    MistakeCategory.TACTICAL_VISION: "Tactical patterns going missed in the middlegame",
    MistakeCategory.POSITIONAL_PLAY: "Positional decisions slipping in the middlegame",
    MistakeCategory.ENDGAME_TECHNIQUE: "Errors creeping into the endgame",
}

_MICROTASKS: dict[str, str] = {
    MistakeCategory.OPENING_PREPARATION: (
        "Pick your single most-played opening from this week and review its "
        "first 10 moves against the main theory line. Drill any deviations "
        "in an opening trainer for 15 minutes a day."
    ),
    MistakeCategory.TACTICAL_VISION: (
        "Solve 25 tactical puzzles a day rated 100–200 points above your "
        "current rating, focused on forks, pins, skewers, and back-rank mates."
    ),
    MistakeCategory.POSITIONAL_PLAY: (
        "Annotate one master game in your weakest opening this week: write "
        "a one-line plan for every move from 8 through 25."
    ),
    MistakeCategory.ENDGAME_TECHNIQUE: (
        "Drill king-and-pawn versus king (opposition + key squares) and the "
        "Lucena and Philidor rook endings for 10 minutes a day."
    ),
}


def _pick_top_holes(category_scores: dict[str, float]) -> list[tuple[str, float]]:
    """Return up to ``MAX_HOLES`` (category, score) pairs, descending by score.

    Zero-scored categories are excluded. Ties are broken alphabetically by
    category name so the output is fully deterministic. Categories not
    covered by ``_HOLE_TITLES`` / ``_MICROTASKS`` are dropped defensively
    so an unknown category from a future schema change cannot leak an
    unmapped row to clients.
    """
    candidates = [
        (cat, score)
        for cat, score in category_scores.items()
        if score > 0.0 and cat in _HOLE_TITLES and cat in _MICROTASKS
    ]
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return candidates[:MAX_HOLES]


def build_weekly_digest(
    db: DBSession,
    player_id: str,
    *,
    now: datetime | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    """Produce the weekly digest payload for ``player_id``.

    Reads the player's ``GameEvent`` rows whose ``created_at`` falls in
    the closed-open window ``[now - window_days, now)``, decodes the
    stored weakness vectors, and runs the existing aggregation pipeline.

    A side effect is that ``HistoricalAnalysisPipeline.run`` logs a
    ``MISTAKE_PATTERN_RECORDED`` analytics event — this matches the
    existing ``/player/progress`` behaviour and keeps the digest's
    aggregation visible to downstream analytics.

    Returns a dict with stable shape:
        period_start, period_end : ISO timestamps
        games_analyzed           : int
        holes                    : list of {category, score, title}
        tasks                    : list of {category, task}
    """
    if now is None:
        now = datetime.utcnow()
    period_start = now - timedelta(days=window_days)

    games = (
        db.query(GameEvent)
        .filter(
            GameEvent.player_id == player_id,
            GameEvent.created_at >= period_start,
            GameEvent.created_at < now,
        )
        .order_by(GameEvent.created_at.desc())
        .all()
    )

    if not games:
        return {
            "period_start": period_start,
            "period_end": now,
            "games_analyzed": 0,
            "holes": [],
            "tasks": [],
        }

    stats = HistoricalAnalysisPipeline(db).run(player_id, games)

    top = _pick_top_holes(stats.category_scores)

    holes = [
        {
            "category": category,
            "score": round(score, 4),
            "title": _HOLE_TITLES[category],
        }
        for category, score in top
    ]
    tasks = [
        {
            "category": category,
            "task": _MICROTASKS[category],
        }
        for category, _ in top
    ]

    return {
        "period_start": period_start,
        "period_end": now,
        "games_analyzed": stats.games_analyzed,
        "holes": holes,
        "tasks": tasks,
    }


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def serialize_digest(record: WeeklyDigest) -> dict[str, Any]:
    """Convert a persisted ``WeeklyDigest`` row into JSON-friendly form."""
    return {
        "id": record.id,
        "player_id": record.player_id,
        "period_start": _to_iso(record.period_start),
        "period_end": _to_iso(record.period_end),
        "games_analyzed": record.games_analyzed,
        "holes": list(record.holes or []),
        "tasks": list(record.tasks or []),
        "generated_at": _to_iso(record.generated_at),
    }


def persist_weekly_digest(
    db: DBSession,
    player_id: str,
    digest: dict[str, Any],
) -> WeeklyDigest:
    """Persist a builder output and return the inserted row."""
    record = WeeklyDigest(
        player_id=player_id,
        period_start=digest["period_start"],
        period_end=digest["period_end"],
        games_analyzed=int(digest["games_analyzed"]),
        holes=list(digest["holes"]),
        tasks=list(digest["tasks"]),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_latest_digest(db: DBSession, player_id: str) -> WeeklyDigest | None:
    """Most recently generated digest for ``player_id``, or ``None``."""
    return (
        db.query(WeeklyDigest)
        .filter(WeeklyDigest.player_id == player_id)
        .order_by(WeeklyDigest.generated_at.desc())
        .first()
    )
