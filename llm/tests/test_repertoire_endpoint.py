"""
Backend tests for GET /repertoire — opening repertoire list backing
the AtriumOpenings screen.

Pinned invariants
-----------------
 1. REP_DEFAULTS_ON_EMPTY:        a fresh player (nothing saved) gets
                                   the 4-entry canonical default list.
 2. REP_DEFAULTS_NOT_PERSISTED:   GET is side-effect-free — the
                                   defaults are NOT inserted on read.
 3. REP_SAVED_OVERRIDES_DEFAULTS: when a player has stored rows, the
                                   GET returns those, NOT the defaults.
 4. REP_ORDER_BY_ORDINAL:         stored rows come back in ordinal ASC.
 5. REP_FILTERS_BY_PLAYER:        one player's openings don't leak to
                                   another.
 6. REP_RESPONSE_SHAPE:           {"openings": [...]} envelope, each
                                   entry has the documented field set.
 7. REP_DEFAULT_HAS_EXACTLY_ONE_ACTIVE: the canonical defaults always
                                   have exactly one is_active=True
                                   entry (matches the OpeningsActivity
                                   companion test).
 8. REP_DEFAULT_MIRRORS_ANDROID:  the default ECOs match the Android
                                   client's DEFAULT_REPERTOIRE 1-for-1
                                   so first-vs-second-visit don't
                                   show different defaults.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("SECA_API_KEY", "ci-test-key")
os.environ.setdefault("SECA_ENV", "dev")
os.environ.setdefault("SECRET_KEY", "ci-secret-key-that-is-32-chars-long!!")


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Same temp-db pattern as test_game_checkpoint."""
    db_file = tmp_path / "seca-test.db"
    monkeypatch.setattr("llm.seca.storage.db.DB_PATH", db_file)
    from llm.seca.storage.db import init_db
    init_db()
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE IF NOT EXISTS players (id TEXT PRIMARY KEY, email TEXT)")
    conn.commit()
    conn.close()
    yield db_file


def _ensure_player(player_id: str = "player-rep") -> str:
    from llm.seca.storage.repo import ensure_player
    ensure_player(player_id)
    return player_id


def _player_namespace(id="player-rep"):
    from types import SimpleNamespace
    return SimpleNamespace(id=id)


def _fake_request():
    from starlette.requests import Request
    return Request({
        "type": "http", "method": "GET", "path": "/repertoire",
        "headers": [], "client": ("127.0.0.1", 0),
    })


def _disable_limiter():
    from llm.seca.shared_limiter import limiter
    return limiter


def _call_get_repertoire(player):
    from llm.server import get_repertoire
    limiter = _disable_limiter()
    prev = limiter.enabled
    limiter.enabled = False
    try:
        return get_repertoire(request=_fake_request(), player=player)
    finally:
        limiter.enabled = prev


# ---------------------------------------------------------------------------
# 1.  Default-on-empty behaviour
# ---------------------------------------------------------------------------


class TestRepertoireDefaults:
    def test_fresh_player_gets_canonical_defaults(self, temp_db):
        """REP_DEFAULTS_ON_EMPTY."""
        _ensure_player()
        result = _call_get_repertoire(_player_namespace())
        assert "openings" in result
        assert len(result["openings"]) == 4
        ecos = [o["eco"] for o in result["openings"]]
        assert ecos == ["C84", "B22", "D02", "A04"]

    def test_defaults_not_persisted_on_read(self, temp_db):
        """REP_DEFAULTS_NOT_PERSISTED — calling GET twice with no
        storage between must not have populated the table."""
        _ensure_player()
        from llm.seca.storage.repo import list_repertoire

        _call_get_repertoire(_player_namespace())
        # Repo-level read should still see zero rows for this player.
        assert list_repertoire("player-rep") == []

        _call_get_repertoire(_player_namespace())
        assert list_repertoire("player-rep") == []

    def test_default_has_exactly_one_active(self, temp_db):
        """REP_DEFAULT_HAS_EXACTLY_ONE_ACTIVE — matches the Android
        client's OpeningsActivityTest invariant."""
        _ensure_player()
        result = _call_get_repertoire(_player_namespace())
        actives = [o for o in result["openings"] if o["is_active"]]
        assert len(actives) == 1, f"expected 1 active line, got {len(actives)}"

    def test_default_mirrors_android_companion(self, temp_db):
        """REP_DEFAULT_MIRRORS_ANDROID — drift here would show users
        different ECOs on first vs subsequent visits."""
        from llm.server import DEFAULT_REPERTOIRE
        _ensure_player()
        result = _call_get_repertoire(_player_namespace())
        assert result["openings"] == DEFAULT_REPERTOIRE


# ---------------------------------------------------------------------------
# 2.  Saved-overrides-defaults + ordering + isolation
# ---------------------------------------------------------------------------


class TestRepertoireStorage:
    def _insert(self, db_file, **fields):
        """Direct SQL insert — bypasses repo (no insert helper yet) so
        these tests can exercise the read path against known state."""
        defaults = {
            "player_id": "player-rep",
            "eco": "C84",
            "name": "Ruy Lopez",
            "line": "1.e4 e5",
            "mastery": 0.5,
            "is_active": 0,
            "ordinal": 0,
        }
        defaults.update(fields)
        conn = sqlite3.connect(db_file)
        conn.execute(
            """
            INSERT INTO repertoire (player_id, eco, name, line, mastery, is_active, ordinal)
            VALUES (:player_id, :eco, :name, :line, :mastery, :is_active, :ordinal)
            """,
            defaults,
        )
        conn.commit()
        conn.close()

    def test_saved_overrides_defaults(self, temp_db):
        """REP_SAVED_OVERRIDES_DEFAULTS — once the player has even one
        saved row, the defaults are NOT mixed in."""
        _ensure_player()
        self._insert(temp_db, eco="X99", name="My Custom Line", ordinal=0)
        result = _call_get_repertoire(_player_namespace())
        assert len(result["openings"]) == 1
        assert result["openings"][0]["eco"] == "X99"

    def test_order_by_ordinal_ascending(self, temp_db):
        """REP_ORDER_BY_ORDINAL — display order is stable."""
        _ensure_player()
        self._insert(temp_db, eco="A1", ordinal=2)
        self._insert(temp_db, eco="A2", ordinal=0)
        self._insert(temp_db, eco="A3", ordinal=1)

        ecos = [o["eco"] for o in _call_get_repertoire(_player_namespace())["openings"]]
        assert ecos == ["A2", "A3", "A1"]

    def test_filters_by_player(self, temp_db):
        """REP_FILTERS_BY_PLAYER — player A's openings must not leak
        to player B."""
        _ensure_player("player-a")
        _ensure_player("player-b")
        self._insert(temp_db, player_id="player-a", eco="A1")

        # B has no rows — falls through to defaults
        result_b = _call_get_repertoire(_player_namespace("player-b"))
        ecos = [o["eco"] for o in result_b["openings"]]
        assert ecos == ["C84", "B22", "D02", "A04"]  # canonical defaults

        # A sees only their own
        result_a = _call_get_repertoire(_player_namespace("player-a"))
        assert [o["eco"] for o in result_a["openings"]] == ["A1"]


# ---------------------------------------------------------------------------
# 3.  Response shape
# ---------------------------------------------------------------------------


class TestRepertoireResponseShape:
    def test_envelope_is_openings(self, temp_db):
        """REP_RESPONSE_SHAPE — top-level key is 'openings' so the
        client can add metadata (count / pagination cursor / etc.)
        later without a breaking change."""
        _ensure_player()
        result = _call_get_repertoire(_player_namespace())
        assert isinstance(result, dict)
        assert list(result.keys()) == ["openings"]

    def test_each_entry_has_documented_fields(self, temp_db):
        _ensure_player()
        result = _call_get_repertoire(_player_namespace())
        required = {"eco", "name", "line", "mastery", "is_active", "ordinal"}
        for entry in result["openings"]:
            missing = required - set(entry.keys())
            assert not missing, f"entry missing fields: {missing} in {entry}"
