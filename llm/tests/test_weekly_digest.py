"""
Tests for the weekly coaching digest (agent v1).

Covered invariants
------------------
 1. EMPTY_WINDOW_PRODUCES_EMPTY_DIGEST
 2. TOP_THREE_HOLES_BY_SCORE
 3. ZERO_SCORED_CATEGORIES_EXCLUDED
 4. SEVEN_DAY_WINDOW_FILTERS_OUT_OLD_GAMES
 5. SEVEN_DAY_WINDOW_KEEPS_RECENT_GAMES
 6. HOLES_PAIR_WITH_TASKS_BY_CATEGORY
 7. EACH_HOLE_HAS_TITLE_AND_SCORE
 8. EACH_TASK_HAS_NON_TRIVIAL_TEXT
 9. TIES_BROKEN_DETERMINISTICALLY
10. PERSIST_WRITES_ROW
11. GET_LATEST_RETURNS_NEWEST
12. REFRESH_ENDPOINT_ROUND_TRIPS
13. FETCH_ENDPOINT_404_WITHOUT_DIGEST
14. DIGEST_USES_NO_LLM_IMPORTS

These are deterministic property tests — they pin behavior, not text.
The microtask copy is allowed to evolve as long as it stays non-trivial
and category-mapped.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

os.environ.setdefault("SECA_API_KEY", "ci-test-key")
os.environ.setdefault("SECA_ENV", "dev")
os.environ.setdefault("SECRET_KEY", "ci-secret-key-that-is-32-chars-long!!")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llm.seca.auth.models import Base
import llm.seca.auth.models  # noqa: F401
import llm.seca.events.models  # noqa: F401
import llm.seca.brain.models  # noqa: F401
import llm.seca.analytics.models  # noqa: F401

from llm.seca.analytics.mistake_stats import MistakeCategory
from llm.seca.analytics.models import WeeklyDigest
from llm.seca.events.models import GameEvent
from llm.seca.coach import weekly_digest as wd
from llm.seca.coach.weekly_digest import (
    DEFAULT_WINDOW_DAYS,
    MAX_HOLES,
    build_weekly_digest,
    get_latest_digest,
    persist_weekly_digest,
    serialize_digest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """Fresh in-memory SQLite session per test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def _seed_game(
    session,
    *,
    player_id: str = "p1",
    weaknesses: dict | None = None,
    created_at: datetime | None = None,
    pgn: str = "1. e4 e5 *",
    result: str = "win",
    accuracy: float = 0.7,
) -> GameEvent:
    event = GameEvent(
        player_id=player_id,
        pgn=pgn,
        result=result,
        accuracy=accuracy,
        weaknesses_json=json.dumps(weaknesses or {}),
        created_at=created_at or datetime.utcnow(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


# ---------------------------------------------------------------------------
# 1. EMPTY_WINDOW_PRODUCES_EMPTY_DIGEST
# ---------------------------------------------------------------------------


def test_empty_window_produces_empty_digest(db_session):
    """No games in DB → games_analyzed=0, no holes, no tasks."""
    digest = build_weekly_digest(db_session, player_id="p1")
    assert digest["games_analyzed"] == 0
    assert digest["holes"] == []
    assert digest["tasks"] == []


def test_other_players_games_excluded(db_session):
    """Games belonging to other players are not aggregated."""
    _seed_game(db_session, player_id="other", weaknesses={"opening": 0.5})
    digest = build_weekly_digest(db_session, player_id="p1")
    assert digest["games_analyzed"] == 0
    assert digest["holes"] == []


# ---------------------------------------------------------------------------
# 2. TOP_THREE_HOLES_BY_SCORE & related selection rules
# ---------------------------------------------------------------------------


def test_top_three_holes_by_score(db_session):
    """All four categories non-zero → exactly 3 holes, ordered by score desc."""
    _seed_game(
        db_session,
        weaknesses={"opening": 0.40, "middlegame": 0.20, "endgame": 0.10},
    )
    digest = build_weekly_digest(db_session, player_id="p1")
    assert digest["games_analyzed"] == 1
    assert len(digest["holes"]) == MAX_HOLES
    scores = [h["score"] for h in digest["holes"]]
    assert scores == sorted(scores, reverse=True), f"holes not score-desc: {scores}"


def test_zero_scored_categories_excluded(db_session):
    """A category whose derived score is 0 must not appear in holes."""
    # Only "opening" non-zero → only opening_preparation has a score.
    _seed_game(db_session, weaknesses={"opening": 0.20})
    digest = build_weekly_digest(db_session, player_id="p1")
    assert len(digest["holes"]) == 1
    assert digest["holes"][0]["category"] == MistakeCategory.OPENING_PREPARATION


def test_ties_broken_deterministically():
    """When two categories tie on score, alphabetical category name wins.

    Tested directly against the selection helper to avoid float-arithmetic
    artifacts from the phase→category derivation that would mask a true
    tie. The selection helper IS the contract here.
    """
    scores = {
        MistakeCategory.TACTICAL_VISION: 0.05,
        MistakeCategory.ENDGAME_TECHNIQUE: 0.05,  # tie with tactical_vision
        MistakeCategory.POSITIONAL_PLAY: 0.10,  # strictly higher
    }
    picked = wd._pick_top_holes(scores)
    cats = [c for c, _ in picked]
    assert cats[0] == MistakeCategory.POSITIONAL_PLAY
    # endgame_technique < tactical_vision alphabetically → endgame first.
    assert cats[1] == MistakeCategory.ENDGAME_TECHNIQUE
    assert cats[2] == MistakeCategory.TACTICAL_VISION


# ---------------------------------------------------------------------------
# 3. SEVEN_DAY window
# ---------------------------------------------------------------------------


def test_seven_day_window_filters_out_old_games(db_session):
    """Games older than 7d from `now` are excluded."""
    now = datetime(2026, 5, 18, 12, 0, 0)
    old = now - timedelta(days=8)
    _seed_game(db_session, weaknesses={"opening": 0.50}, created_at=old)
    digest = build_weekly_digest(db_session, player_id="p1", now=now)
    assert digest["games_analyzed"] == 0
    assert digest["holes"] == []


def test_seven_day_window_keeps_recent_games(db_session):
    """Games within the last 7d are aggregated."""
    now = datetime(2026, 5, 18, 12, 0, 0)
    recent = now - timedelta(days=2)
    _seed_game(db_session, weaknesses={"opening": 0.50}, created_at=recent)
    digest = build_weekly_digest(db_session, player_id="p1", now=now)
    assert digest["games_analyzed"] == 1


def test_window_boundary_includes_exactly_7d_old(db_session):
    """Game at exactly now-7d boundary is included (>= filter)."""
    now = datetime(2026, 5, 18, 12, 0, 0)
    on_boundary = now - timedelta(days=DEFAULT_WINDOW_DAYS)
    _seed_game(db_session, weaknesses={"opening": 0.20}, created_at=on_boundary)
    digest = build_weekly_digest(db_session, player_id="p1", now=now)
    assert digest["games_analyzed"] == 1


def test_window_boundary_excludes_future_games(db_session):
    """Games at or after `now` are excluded (< filter, half-open window)."""
    now = datetime(2026, 5, 18, 12, 0, 0)
    _seed_game(db_session, weaknesses={"opening": 0.20}, created_at=now)
    digest = build_weekly_digest(db_session, player_id="p1", now=now)
    assert digest["games_analyzed"] == 0


# ---------------------------------------------------------------------------
# 4. HOLES_PAIR_WITH_TASKS / shape contracts
# ---------------------------------------------------------------------------


def test_holes_pair_with_tasks_by_category(db_session):
    """Holes and tasks must be the same length and ordered by matching category."""
    _seed_game(
        db_session,
        weaknesses={"opening": 0.30, "middlegame": 0.20, "endgame": 0.15},
    )
    digest = build_weekly_digest(db_session, player_id="p1")
    assert len(digest["holes"]) == len(digest["tasks"])
    for hole, task in zip(digest["holes"], digest["tasks"]):
        assert hole["category"] == task["category"]


def test_each_hole_has_title_and_score(db_session):
    """Every hole row carries category, score (>= 0), and a non-empty title."""
    _seed_game(db_session, weaknesses={"opening": 0.30, "middlegame": 0.20})
    digest = build_weekly_digest(db_session, player_id="p1")
    for hole in digest["holes"]:
        assert "category" in hole
        assert isinstance(hole["score"], float)
        assert hole["score"] >= 0.0
        assert isinstance(hole["title"], str) and len(hole["title"]) > 0


def test_each_task_has_non_trivial_text(db_session):
    """Microtask strings are specific interventions, not placeholders."""
    _seed_game(
        db_session,
        weaknesses={"opening": 0.30, "middlegame": 0.20, "endgame": 0.10},
    )
    digest = build_weekly_digest(db_session, player_id="p1")
    for task in digest["tasks"]:
        text = task["task"]
        assert isinstance(text, str)
        # 50 chars is well below every template; catches accidental stub.
        assert len(text) > 50, f"task too short for {task['category']}: {text!r}"
        # Catch a regression where a template is reduced to "study X".
        assert not text.lower().startswith("study "), f"placeholder-like text: {text!r}"


def test_every_known_category_has_template():
    """Every MistakeCategory must have both a hole title and microtask."""
    for category in MistakeCategory.ALL:
        assert category in wd._HOLE_TITLES, f"missing hole title for {category}"
        assert category in wd._MICROTASKS, f"missing microtask for {category}"
        assert len(wd._MICROTASKS[category]) > 50


# ---------------------------------------------------------------------------
# 5. Persistence
# ---------------------------------------------------------------------------


def test_persist_writes_row(db_session):
    """persist_weekly_digest commits a row that survives a fresh query."""
    _seed_game(db_session, weaknesses={"opening": 0.30})
    digest = build_weekly_digest(db_session, player_id="p1")
    persisted = persist_weekly_digest(db_session, "p1", digest)

    rows = db_session.query(WeeklyDigest).filter_by(player_id="p1").all()
    assert len(rows) == 1
    assert rows[0].id == persisted.id
    assert rows[0].games_analyzed == digest["games_analyzed"]
    assert rows[0].holes == digest["holes"]
    assert rows[0].tasks == digest["tasks"]


def test_get_latest_digest_returns_newest(db_session):
    """When multiple digests exist, get_latest returns the most recently generated."""
    _seed_game(db_session, weaknesses={"opening": 0.20})
    first = build_weekly_digest(db_session, player_id="p1")
    older = persist_weekly_digest(db_session, "p1", first)

    # Force the second persist to land with a strictly later generated_at.
    later = datetime.utcnow() + timedelta(seconds=5)
    second_record = WeeklyDigest(
        player_id="p1",
        period_start=first["period_start"],
        period_end=first["period_end"],
        games_analyzed=first["games_analyzed"],
        holes=first["holes"],
        tasks=first["tasks"],
        generated_at=later,
    )
    db_session.add(second_record)
    db_session.commit()

    latest = get_latest_digest(db_session, "p1")
    assert latest is not None
    assert latest.id == second_record.id
    assert older.id != latest.id


def test_get_latest_digest_returns_none_for_unknown_player(db_session):
    """Player with no digest history → None."""
    assert get_latest_digest(db_session, "nobody") is None


def test_serialize_digest_returns_iso_timestamps(db_session):
    """serialize_digest emits ISO-format strings, not raw datetimes."""
    _seed_game(db_session, weaknesses={"opening": 0.20})
    digest = build_weekly_digest(db_session, player_id="p1")
    record = persist_weekly_digest(db_session, "p1", digest)
    serial = serialize_digest(record)
    assert isinstance(serial["period_start"], str)
    assert isinstance(serial["period_end"], str)
    assert isinstance(serial["generated_at"], str)
    # ISO format starts with year.
    assert serial["period_start"].startswith("20")


# ---------------------------------------------------------------------------
# 6. Endpoint integration (direct handler call, no auth boundary)
# ---------------------------------------------------------------------------


def _player_stub(player_id: str = "p1"):
    return SimpleNamespace(id=player_id)


def test_refresh_endpoint_round_trips(db_session):
    """POST /weekly-digest/refresh writes a digest; GET returns the same payload."""
    from llm.seca.analytics.router import (
        refresh_weekly_digest,
        fetch_weekly_digest,
    )

    _seed_game(db_session, weaknesses={"opening": 0.30, "middlegame": 0.20})
    refreshed = refresh_weekly_digest(player=_player_stub(), db=db_session)
    fetched = fetch_weekly_digest(player=_player_stub(), db=db_session)

    assert refreshed["id"] == fetched["id"]
    assert refreshed["holes"] == fetched["holes"]
    assert refreshed["tasks"] == fetched["tasks"]
    assert refreshed["games_analyzed"] == fetched["games_analyzed"] == 1


def test_fetch_endpoint_404_without_digest(db_session):
    """GET /weekly-digest with no prior refresh → 404."""
    from fastapi import HTTPException
    from llm.seca.analytics.router import fetch_weekly_digest

    with pytest.raises(HTTPException) as exc:
        fetch_weekly_digest(player=_player_stub(), db=db_session)
    assert exc.value.status_code == 404


def test_refresh_with_no_games_persists_empty_digest(db_session):
    """POST refresh with no in-window games still writes a digest (games_analyzed=0)."""
    from llm.seca.analytics.router import refresh_weekly_digest

    refreshed = refresh_weekly_digest(player=_player_stub(), db=db_session)
    assert refreshed["games_analyzed"] == 0
    assert refreshed["holes"] == []
    assert refreshed["tasks"] == []
    # And it persists.
    rows = db_session.query(WeeklyDigest).all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 7. No-LLM invariant
# ---------------------------------------------------------------------------


def test_digest_uses_no_llm_imports():
    """The weekly_digest module must not import the LLM stack.

    Project Rule #2: "The LLM explains, but must not override engine
    truth or bypass ESV." Selection + microtask emission for v1 is
    deterministic — any future LLM-rendered preamble belongs in a
    separate module so this invariant holds.
    """
    import inspect

    source = inspect.getsource(wd)
    forbidden = (
        "explain_pipeline",
        "chat_pipeline",
        "httpx",
        "from llm.rag.llm",
        "deepseek",
        "render_mode_2_prompt",
    )
    for needle in forbidden:
        assert needle not in source, f"weekly_digest must not import {needle}"
