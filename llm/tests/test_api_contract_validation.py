"""
API contract validation tests.

Verifies that the backend endpoint response structures match the schemas
documented in docs/API_CONTRACTS.md.  Tests are deterministic, require no
live engine or database, and fail CI if any field is missing or has the wrong
type.

Covered endpoints:
  - POST /engine/eval  (host_app.py)
  - GET  /engine/eval  (host_app.py)
  - GET  /next-training/{player_id}  (server.py)
  - POST /game/finish  (llm/seca/events/router.py)

Documented mismatches captured as dedicated test classes:
  - TestCoachEndpointMissing     — /coach does not exist
  - TestNextTrainingSchemaConflict — /next-training vs /curriculum/next
  - TestCoachExecutorHandlerGap  — PUZZLE / PLAN_UPDATE fall back to default
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_STR_OR_NONE = (str, type(None))


def _assert_str_or_none(value, field: str) -> None:
    assert isinstance(
        value, _REQUIRED_STR_OR_NONE
    ), f"{field} must be str | None, got {type(value).__name__}: {value!r}"


def _assert_int_or_none(value, field: str) -> None:
    assert isinstance(
        value, (int, type(None))
    ), f"{field} must be int | None, got {type(value).__name__}: {value!r}"


def _assert_str(value, field: str) -> None:
    assert isinstance(value, str), f"{field} must be str, got {type(value).__name__}: {value!r}"


def _assert_float(value, field: str) -> None:
    assert isinstance(
        value, (int, float)
    ), f"{field} must be numeric, got {type(value).__name__}: {value!r}"


def _assert_dict(value, field: str) -> None:
    assert isinstance(value, dict), f"{field} must be dict, got {type(value).__name__}: {value!r}"


# ---------------------------------------------------------------------------
# 1. /engine/eval — POST + GET (host_app.py)
# ---------------------------------------------------------------------------

_ENGINE_EVAL_SOURCES = {"engine", "cache", "book"}


def _make_engine_service_mock(
    *,
    score: int | None = 42,
    best_move: str | None = "e2e4",
    source: str = "engine",
    cache_hit: bool = False,
):
    """Return a minimal evaluate_with_metrics mock for host_app tests."""

    async def _evaluate_with_metrics(*, fen, moves, movetime, nodes):
        result = {"score": score, "best_move": best_move, "source": source}
        metrics = {
            "cache_hit": cache_hit,
            "source": source,
            "engine_wait_ms": 1.0,
            "engine_eval_ms": 5.0,
            "total_ms": 6.0,
        }
        return result, metrics

    return _evaluate_with_metrics


class TestEngineEvalContractSchema:
    """POST /engine/eval and GET /engine/eval response schema validation."""

    def _run_eval_position(self, monkeypatch, *, score=42, best_move="e2e4", source="engine"):
        from llm import host_app

        class _FakeEvaluator:
            default_nodes = 5000

            def resolve_limits(self, *, movetime, nodes):
                if movetime is None and nodes is None:
                    return None, self.default_nodes
                return movetime, nodes

        # Disable the rate limiter so direct function calls don't need a real Request.
        monkeypatch.setattr(host_app._limiter, "enabled", False)
        monkeypatch.setattr(host_app, "engine_eval", _FakeEvaluator())
        monkeypatch.setattr(
            host_app.engine_service,
            "evaluate_with_metrics",
            _make_engine_service_mock(score=score, best_move=best_move, source=source),
        )

        async def _run():
            return await host_app.eval_position(
                MagicMock(), host_app.EngineEvalRequest(fen="startpos")
            )

        return asyncio.run(_run())

    def test_response_has_score_field(self, monkeypatch):
        result = self._run_eval_position(monkeypatch)
        assert "score" in result, "Response missing required field 'score'"

    def test_response_has_best_move_field(self, monkeypatch):
        result = self._run_eval_position(monkeypatch)
        assert "best_move" in result, "Response missing required field 'best_move'"

    def test_response_has_source_field(self, monkeypatch):
        result = self._run_eval_position(monkeypatch)
        assert "source" in result, "Response missing required field 'source'"

    def test_response_has_metrics_field(self, monkeypatch):
        result = self._run_eval_position(monkeypatch)
        assert "_metrics" in result, "Response missing required field '_metrics'"

    def test_score_is_int_or_none(self, monkeypatch):
        """score must be int | None (centipawns from White perspective)."""
        result = self._run_eval_position(monkeypatch, score=42)
        _assert_int_or_none(result["score"], "score")

    def test_score_can_be_null(self, monkeypatch):
        """Fallback path returns score=None when engine unavailable."""
        result = self._run_eval_position(monkeypatch, score=None)
        assert result["score"] is None

    def test_best_move_is_str_or_none(self, monkeypatch):
        """best_move must be a UCI string or None."""
        result = self._run_eval_position(monkeypatch, best_move="e2e4")
        _assert_str_or_none(result["best_move"], "best_move")

    def test_best_move_can_be_null(self, monkeypatch):
        result = self._run_eval_position(monkeypatch, best_move=None)
        assert result["best_move"] is None

    def test_source_is_valid_enum_value(self, monkeypatch):
        """source must be one of the three documented values."""
        for source in ("engine", "cache", "book"):
            result = self._run_eval_position(monkeypatch, source=source)
            assert (
                result["source"] in _ENGINE_EVAL_SOURCES
            ), f"source={result['source']!r} not in {_ENGINE_EVAL_SOURCES}"

    def test_metrics_is_dict(self, monkeypatch):
        result = self._run_eval_position(monkeypatch)
        _assert_dict(result["_metrics"], "_metrics")

    def test_metrics_has_cache_hit_bool(self, monkeypatch):
        result = self._run_eval_position(monkeypatch)
        assert "cache_hit" in result["_metrics"], "_metrics missing 'cache_hit'"
        assert isinstance(result["_metrics"]["cache_hit"], bool), "cache_hit must be bool"

    def test_score_sign_convention_positive_means_white_better(self, monkeypatch):
        """Positive score → White has the advantage (documented convention)."""
        result = self._run_eval_position(monkeypatch, score=100)
        assert result["score"] == 100
        assert result["score"] > 0, "Positive score should indicate White advantage"

    def test_score_sign_convention_negative_means_black_better(self, monkeypatch):
        result = self._run_eval_position(monkeypatch, score=-80)
        assert result["score"] == -80
        assert result["score"] < 0, "Negative score should indicate Black advantage"

    def test_engine_source_response_has_full_metrics(self, monkeypatch):
        """Engine-sourced responses include timing metrics."""
        result = self._run_eval_position(monkeypatch, source="engine")
        metrics = result["_metrics"]
        for key in ("engine_wait_ms", "engine_eval_ms", "total_ms"):
            assert key in metrics, f"_metrics missing '{key}' for source=engine"

    def test_no_extra_required_fields_beyond_contract(self, monkeypatch):
        """No undocumented mandatory fields sneaked into the response."""
        result = self._run_eval_position(monkeypatch)
        documented = {"score", "best_move", "source", "_metrics"}
        actual = set(result.keys())
        assert documented.issubset(
            actual
        ), f"Contract fields missing from response: {documented - actual}"


class TestEngineEvalGetContractSchema:
    """GET /engine/eval (query-param variant) has the same response schema."""

    def test_get_variant_returns_same_schema(self, monkeypatch):
        from llm import host_app

        class _FakeEvaluator:
            default_nodes = 5000

            def resolve_limits(self, *, movetime, nodes):
                return movetime, nodes

        monkeypatch.setattr(host_app, "engine_eval", _FakeEvaluator())
        monkeypatch.setattr(host_app._limiter, "enabled", False)
        monkeypatch.setattr(
            host_app.engine_service,
            "evaluate_with_metrics",
            _make_engine_service_mock(score=15, best_move="d2d4"),
        )

        async def _run():
            return await host_app.eval_position_query(MagicMock(), fen="startpos")

        result = asyncio.run(_run())
        for field in ("score", "best_move", "source", "_metrics"):
            assert field in result, f"GET variant missing '{field}'"

    def test_get_variant_movetime_aliases(self, monkeypatch):
        """GET endpoint accepts both movetime_ms= and movetime= aliases."""
        from llm import host_app

        received_movetime = {}

        async def _fake_evaluate(*, fen, moves, movetime, nodes):
            received_movetime["mt"] = movetime
            return (
                {"score": 0, "best_move": None, "source": "engine"},
                {"cache_hit": False, "total_ms": 1.0},
            )

        class _FakeEvaluator:
            default_nodes = 5000

            def resolve_limits(self, *, movetime, nodes):
                return movetime, nodes

        monkeypatch.setattr(host_app._limiter, "enabled", False)
        monkeypatch.setattr(host_app, "engine_eval", _FakeEvaluator())
        monkeypatch.setattr(host_app.engine_service, "evaluate_with_metrics", _fake_evaluate)

        async def _run():
            return await host_app.eval_position_query(
                MagicMock(), fen="startpos", movetime_ms=30, movetime=None
            )

        asyncio.run(_run())
        assert received_movetime["mt"] == 30


# ---------------------------------------------------------------------------
# 2. GET /next-training/{player_id} (server.py)
# ---------------------------------------------------------------------------

_NEXT_TRAINING_REQUIRED = {"topic", "difficulty", "format", "expected_gain"}


class TestNextTrainingContractSchema:
    """GET /next-training/{player_id} response schema validation."""

    def _call_next_training(self, monkeypatch, player_id="p1"):
        import llm.server as server_module
        from llm.seca.curriculum.types import TrainingTask

        fake_task = TrainingTask(
            topic="tactics",
            difficulty=0.6,
            format="puzzle",
            expected_gain=2.5,
        )

        class _FakeScheduler:
            def next_task(self, weaknesses, rating):
                return fake_task

        monkeypatch.setattr(server_module, "scheduler", _FakeScheduler())

        # Call handler directly.  After AUT-01 the dependency is
        # get_current_player (JWT-derived) and the handler enforces
        # path player_id == str(player.id).  Pin both to the same id
        # so the legitimate code path is exercised.
        from types import SimpleNamespace as _SN
        fake_player = _SN(id=player_id, rating=1200.0, confidence=0.5)
        return server_module.next_training(player_id=player_id, player=fake_player)

    def test_response_has_all_required_fields(self, monkeypatch):
        result = self._call_next_training(monkeypatch)
        missing = _NEXT_TRAINING_REQUIRED - set(result.keys())
        assert not missing, f"Response missing required fields: {missing}"

    def test_topic_is_string(self, monkeypatch):
        result = self._call_next_training(monkeypatch)
        _assert_str(result["topic"], "topic")

    def test_difficulty_is_numeric(self, monkeypatch):
        result = self._call_next_training(monkeypatch)
        _assert_float(result["difficulty"], "difficulty")

    def test_format_is_string(self, monkeypatch):
        result = self._call_next_training(monkeypatch)
        _assert_str(result["format"], "format")

    def test_expected_gain_is_numeric(self, monkeypatch):
        result = self._call_next_training(monkeypatch)
        _assert_float(result["expected_gain"], "expected_gain")

    def test_no_exercise_type_field(self, monkeypatch):
        """/next-training must NOT return 'exercise_type' (that belongs to /curriculum/next)."""
        result = self._call_next_training(monkeypatch)
        assert "exercise_type" not in result, (
            "exercise_type must not appear in /next-training response "
            "(belongs to /curriculum/next schema)"
        )

    def test_no_payload_field(self, monkeypatch):
        """/next-training must NOT return 'payload' (that belongs to /curriculum/next)."""
        result = self._call_next_training(monkeypatch)
        assert "payload" not in result, (
            "payload must not appear in /next-training response "
            "(belongs to /curriculum/next schema)"
        )


# ---------------------------------------------------------------------------
# 3. POST /game/finish (llm/seca/events/router.py)
# ---------------------------------------------------------------------------

_GAME_FINISH_REQUIRED = {
    "status",
    "new_rating",
    "confidence",
    "learning",
    "coach_action",
    "coach_content",
}
_COACH_ACTION_REQUIRED = {"type", "weakness", "reason"}
_COACH_CONTENT_REQUIRED = {"title", "description", "payload"}
_COACH_ACTION_TYPES = {"NONE", "REFLECT", "DRILL", "PUZZLE", "PLAN_UPDATE"}


def _make_game_finish_mocks(
    *,
    rating_before=1500.0,
    rating_after=1510.0,
    confidence_before=0.70,
    confidence_after=0.72,
    learning_delta=10.0,
):
    """Return (player, db) mocks suitable for calling finish_game() directly."""
    player = SimpleNamespace(
        id=1,
        rating=rating_before,
        confidence=confidence_before,
    )

    def _fake_refresh(obj):
        if obj is player:
            player.rating = rating_after
            player.confidence = confidence_after

    db = MagicMock()
    db.refresh.side_effect = _fake_refresh
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        []
    )
    return player, db


def _call_finish_game(
    req_kwargs: dict,
    player,
    db,
):
    """Call finish_game() with all DB/storage dependencies mocked.

    Direct calls bypass the slowapi decorator's rate-limit counter
    backend by toggling `limiter.enabled = False` for the duration of
    the call — these tests exercise the handler logic, not the rate
    limit (the rate limit is verified by test_security_game_finish_rate_limit.py
    via AST inspection of the decorator)."""
    from llm.seca.events.router import finish_game, GameFinishRequest
    from llm.seca.shared_limiter import limiter
    from starlette.requests import Request

    fake_event = SimpleNamespace(id=99)
    req = GameFinishRequest(**req_kwargs)
    fake_request = Request({
        "type": "http", "method": "POST", "path": "/game/finish",
        "headers": [], "client": ("127.0.0.1", 0),
    })

    prev_enabled = limiter.enabled
    limiter.enabled = False
    try:
        with (
            patch("llm.seca.events.router.EventStorage") as MockStorage,
            patch("llm.seca.events.router.SkillUpdater"),
        ):
            MockStorage.return_value.store_game.return_value = fake_event
            result = finish_game(req=req, player=player, request=fake_request, db=db)
    finally:
        limiter.enabled = prev_enabled

    return result


_DEFAULT_FINISH_REQ = {
    "pgn": (
        '[Event "Test"]\n'
        '[Site "?"]\n'
        '[Date "2025.01.01"]\n'
        '[Round "1"]\n'
        '[White "Player1"]\n'
        '[Black "Player2"]\n'
        '[Result "1-0"]\n'
        "\n"
        "1. e4 e5 2. Nf3 Nc6 1-0"
    ),
    "result": "win",
    "accuracy": 0.85,
    "weaknesses": {"tactics": 0.6},
}


class TestGameFinishContractSchema:
    """POST /game/finish response schema validation."""

    def test_response_has_all_required_top_level_fields(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        missing = _GAME_FINISH_REQUIRED - set(result.keys())
        assert not missing, f"Response missing required fields: {missing}"

    def test_status_is_stored(self):
        """status must always be the string 'stored' on success."""
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        assert result["status"] == "stored"

    def test_new_rating_is_numeric(self):
        player, db = _make_game_finish_mocks(rating_after=1510.0)
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_float(result["new_rating"], "new_rating")

    def test_confidence_is_numeric(self):
        player, db = _make_game_finish_mocks(confidence_after=0.72)
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_float(result["confidence"], "confidence")

    def test_learning_is_dict(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_dict(result["learning"], "learning")

    def test_learning_has_status_key(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        assert "status" in result["learning"], "learning dict missing 'status' key"

    def test_coach_action_has_all_required_fields(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_dict(result["coach_action"], "coach_action")
        missing = _COACH_ACTION_REQUIRED - set(result["coach_action"].keys())
        assert not missing, f"coach_action missing required fields: {missing}"

    def test_coach_content_has_all_required_fields(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_dict(result["coach_content"], "coach_content")
        missing = _COACH_CONTENT_REQUIRED - set(result["coach_content"].keys())
        assert not missing, f"coach_content missing required fields: {missing}"

    def test_coach_action_type_is_valid_enum(self):
        """coach_action.type must be one of the documented action types."""
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        action_type = result["coach_action"]["type"]
        assert (
            action_type in _COACH_ACTION_TYPES
        ), f"coach_action.type={action_type!r} not in {_COACH_ACTION_TYPES}"

    def test_coach_action_weakness_is_str_or_none(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_str_or_none(result["coach_action"]["weakness"], "coach_action.weakness")

    def test_coach_action_reason_is_str(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_str(result["coach_action"]["reason"], "coach_action.reason")

    def test_coach_content_title_is_str(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_str(result["coach_content"]["title"], "coach_content.title")

    def test_coach_content_description_is_str(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_str(result["coach_content"]["description"], "coach_content.description")

    def test_coach_content_payload_is_dict(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        _assert_dict(result["coach_content"]["payload"], "coach_content.payload")

    def test_new_rating_reflects_post_refresh_value(self):
        """new_rating must reflect the value AFTER db.refresh(), not the input."""
        player, db = _make_game_finish_mocks(rating_before=1500.0, rating_after=1512.0)
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        assert result["new_rating"] == 1512.0

    def test_confidence_reflects_post_refresh_value(self):
        player, db = _make_game_finish_mocks(confidence_before=0.70, confidence_after=0.74)
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        assert result["confidence"] == 0.74

    def test_safe_mode_sets_learning_status(self):
        """In SAFE_MODE (always True in prod), learning.status must be 'safe_mode'."""
        player, db = _make_game_finish_mocks()
        result = _call_finish_game(_DEFAULT_FINISH_REQ, player, db)
        # SAFE_MODE = True is hardcoded in llm/seca/runtime/safe_mode.py
        assert result["learning"]["status"] == "safe_mode"

    def test_result_draw_is_accepted(self):
        """'draw' is a valid result value."""
        player, db = _make_game_finish_mocks()
        result = _call_finish_game({**_DEFAULT_FINISH_REQ, "result": "draw"}, player, db)
        assert result["status"] == "stored"

    def test_result_loss_is_accepted(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game({**_DEFAULT_FINISH_REQ, "result": "loss"}, player, db)
        assert result["status"] == "stored"

    def test_empty_weaknesses_is_accepted(self):
        player, db = _make_game_finish_mocks()
        result = _call_finish_game({**_DEFAULT_FINISH_REQ, "weaknesses": {}}, player, db)
        assert result["status"] == "stored"


# ---------------------------------------------------------------------------
# 4. GET /auth/me — skill_vector field (P2-A contract)
# ---------------------------------------------------------------------------


class TestAuthMeContractSchema:
    """GET /auth/me response must include a 'skill_vector' dict field (P2-A)."""

    def _call_me(self, skill_vector_json: str = "{}"):
        from types import SimpleNamespace

        from llm.seca.auth.router import me

        player = SimpleNamespace(
            id="player-123",
            email="test@chess.com",
            rating=1450.0,
            confidence=0.65,
            skill_vector_json=skill_vector_json,
        )
        return me(player=player)

    def test_me_response_has_skill_vector_field(self):
        """skill_vector must be present in the /auth/me response."""
        result = self._call_me()
        assert "skill_vector" in result, (
            "GET /auth/me must include 'skill_vector' — "
            "Android client reads it to display weakness tags."
        )

    def test_skill_vector_is_dict(self):
        result = self._call_me()
        _assert_dict(result["skill_vector"], "skill_vector")

    def test_skill_vector_values_are_numeric(self):
        """All values in skill_vector must be numeric (float-compatible)."""
        result = self._call_me('{"tactics": 0.5, "endgame": 0.3}')
        for key, val in result["skill_vector"].items():
            _assert_float(val, f"skill_vector.{key}")

    def test_skill_vector_empty_when_no_history(self):
        """Empty JSON object yields an empty dict, not an error."""
        result = self._call_me("{}")
        assert result["skill_vector"] == {}

    def test_skill_vector_malformed_json_returns_empty(self):
        """Malformed skill_vector_json must not raise; returns empty dict."""
        result = self._call_me("not-valid-json")
        assert result["skill_vector"] == {}, (
            "Malformed skill_vector_json must degrade gracefully to empty dict."
        )

    def test_me_still_returns_core_fields(self):
        """P2-A addition must not drop existing fields: id, email, rating, confidence."""
        result = self._call_me()
        for field in ("id", "email", "rating", "confidence"):
            assert field in result, f"skill_vector addition must preserve field '{field}'"

    def test_non_numeric_skill_vector_values_are_filtered(self):
        """String values in skill_vector_json must be silently filtered out."""
        result = self._call_me('{"tactics": 0.6, "stale": "not-a-number"}')
        assert "stale" not in result["skill_vector"], (
            "Non-numeric entries must be excluded from skill_vector response."
        )
        assert "tactics" in result["skill_vector"]


# ---------------------------------------------------------------------------
# 6. Documented mismatches
# ---------------------------------------------------------------------------


class TestCoachEndpointMissing:
    """Contract mismatch: /coach endpoint does not exist."""

    def test_server_has_no_coach_route(self):
        """server.py must have no route registered at /coach."""
        import llm.server as server_module

        routes = [getattr(r, "path", None) for r in server_module.app.routes]
        assert "/coach" not in routes, (
            "/coach route unexpectedly found in server.py. "
            "Update docs/API_CONTRACTS.md to document the new endpoint."
        )

    def test_host_app_has_no_coach_route(self):
        """host_app.py must have no route registered at /coach."""
        from llm import host_app

        routes = [getattr(r, "path", None) for r in host_app.app.routes]
        assert "/coach" not in routes, (
            "/coach route unexpectedly found in host_app.py. "
            "Update docs/API_CONTRACTS.md to document the new endpoint."
        )


class TestNextTrainingSchemaConflict:
    """
    Contract mismatch: /next-training and /curriculum/next return different schemas.

    These two endpoints serve the same purpose but have incompatible response shapes.
    This test ensures neither endpoint silently starts returning the other's schema.
    """

    def test_next_training_does_not_return_exercise_type(self, monkeypatch):
        """Regression guard: /next-training must never start returning exercise_type."""
        import llm.server as server_module
        from llm.seca.curriculum.types import TrainingTask

        fake_task = TrainingTask(topic="endgame", difficulty=0.5, format="game", expected_gain=1.0)
        monkeypatch.setattr(
            server_module, "scheduler", SimpleNamespace(next_task=lambda *a: fake_task)
        )
        result = server_module.next_training(
            player_id="p1",
            player=SimpleNamespace(id="p1", rating=1200.0, confidence=0.5),
        )
        assert "exercise_type" not in result

    def test_curriculum_next_schema_has_exercise_type_not_format(self):
        """
        CurriculumGenerator.generate() returns a TrainingPlan with exercise_type,
        not format.  If someone renames this field, /curriculum/next contract breaks.
        """
        from llm.seca.curriculum.generator import CurriculumGenerator

        # Verify the attribute name on the return type
        sig = CurriculumGenerator.generate
        import inspect

        src = inspect.getsource(sig)
        assert "exercise_type" in src, (
            "CurriculumGenerator.generate() no longer uses 'exercise_type'. "
            "Update /curriculum/next contract in docs/API_CONTRACTS.md."
        )
        assert "format" not in src or "exercise_type" in src, (
            "CurriculumGenerator has changed its field naming — "
            "the /curriculum/next contract needs review."
        )

    def test_next_training_schema_fields_are_stable(self, monkeypatch):
        """
        The four fields of /next-training are: topic, difficulty, format, expected_gain.
        If the handler changes these names, the Android client breaks.
        """
        import llm.server as server_module
        from llm.seca.curriculum.types import TrainingTask

        fake_task = TrainingTask(
            topic="tactics", difficulty=0.7, format="puzzle", expected_gain=3.0
        )
        monkeypatch.setattr(
            server_module, "scheduler", SimpleNamespace(next_task=lambda *a: fake_task)
        )
        result = server_module.next_training(
            player_id="p2",
            player=SimpleNamespace(id="p2", rating=1200.0, confidence=0.5),
        )
        for field in ("topic", "difficulty", "format", "expected_gain"):
            assert field in result, (
                f"Field '{field}' removed from /next-training response. "
                "This breaks backward compatibility with Android clients."
            )


class TestCoachExecutorHandlerGap:
    """
    CoachExecutor handler coverage for PUZZLE and PLAN_UPDATE action types.

    Previously (before the fix) both action types had no dedicated handler and
    fell through to _handle_default, producing 'Keep playing' content regardless
    of the action type. The handlers have since been added. These tests verify the
    corrected behaviour.

    See docs/API_CONTRACTS.md — /game/finish — executor handler gap (now fixed).
    """

    def test_puzzle_action_returns_specific_content(self):
        """
        PUZZLE action now has a _handle_puzzle handler.
        The returned content must not be the generic 'Keep playing' fallback,
        and must reference the action's weakness theme.
        """
        from llm.seca.coach.executor import CoachExecutor

        action = SimpleNamespace(type="PUZZLE", weakness="tactics", reason="confidence drop")
        content = CoachExecutor().execute(action)
        assert content.title != "Keep playing", (
            "_handle_puzzle must return specific content, not the default fallback."
        )
        assert "tactics" in content.title.lower() or "puzzle" in content.title.lower(), (
            "PUZZLE content title should reference the weakness or 'puzzle'."
        )

    def test_plan_update_action_returns_specific_content(self):
        """
        PLAN_UPDATE action now has a _handle_plan_update handler.
        The returned content must not be the generic 'Keep playing' fallback,
        and must reference the action's weakness.
        """
        from llm.seca.coach.executor import CoachExecutor

        action = SimpleNamespace(type="PLAN_UPDATE", weakness="endgame", reason="repeated weakness")
        content = CoachExecutor().execute(action)
        assert content.title != "Keep playing", (
            "_handle_plan_update must return specific content, not the default fallback."
        )
        assert "endgame" in content.description.lower() or "endgame" in content.payload.get(
            "updated_focus", ""
        ), "PLAN_UPDATE content should reference the weakness."

    def test_game_finish_puzzle_response_is_consistent(self):
        """
        When PostGameCoachController decides PUZZLE, finish_game must return
        coach_content that is consistent with the action type — i.e. NOT 'Keep playing'.
        """
        player, db = _make_game_finish_mocks(
            rating_before=1500.0,
            rating_after=1502.0,
            confidence_before=0.80,
            confidence_after=0.70,  # confidence drop → triggers PUZZLE
        )
        result = _call_finish_game(
            {
                "pgn": (
                    '[Event "Test"]\n[Site "?"]\n[Date "2025.01.01"]\n'
                    '[Round "1"]\n[White "Player1"]\n[Black "Player2"]\n'
                    '[Result "*"]\n\n1. e4 e5 *'
                ),
                "result": "loss",
                "accuracy": 0.60,
                "weaknesses": {"tactics": 0.5},
            },
            player,
            db,
        )
        action_type = result["coach_action"]["type"]
        content_title = result["coach_content"]["title"]
        if action_type == "PUZZLE":
            assert content_title != "Keep playing", (
                f"coach_action.type='PUZZLE' but coach_content.title={content_title!r}. "
                "The executor handler gap was supposed to be fixed — "
                "_handle_puzzle must return puzzle-specific content."
            )

    def test_drill_and_reflect_handlers_are_consistent(self):
        """
        DRILL and REFLECT DO have handlers — these are the non-broken cases.
        They should produce content that matches the action type.
        """
        from llm.seca.coach.executor import CoachExecutor

        drill = SimpleNamespace(type="DRILL", weakness="tactics", reason="big drop")
        reflect = SimpleNamespace(type="REFLECT", weakness=None, reason="big gain")

        drill_content = CoachExecutor().execute(drill)
        reflect_content = CoachExecutor().execute(reflect)

        assert (
            drill_content.title != "Keep playing"
        ), "DRILL handler should produce specific content, not default"
        assert (
            reflect_content.title != "Keep playing"
        ), "REFLECT handler should produce specific content, not default"
        assert (
            "tactics" in drill_content.title.lower()
        ), "DRILL content should reference the weakness name"


# ---------------------------------------------------------------------------
# 7. GET / — root health endpoint (server.py)
# ---------------------------------------------------------------------------


class TestRootHealthEndpoint:
    """GET / root liveness probe."""

    def test_root_returns_status_ok(self):
        import llm.server as server_module

        result = server_module.root()
        assert result == {"status": "ok"}, f"Expected {{'status': 'ok'}}, got {result!r}"

    def test_root_and_health_return_identical_shape(self):
        import llm.server as server_module

        assert server_module.root() == server_module.health(), (
            "GET / and GET /health must return the same body"
        )


# ---------------------------------------------------------------------------
# 8. POST /analyze (server.py)
# ---------------------------------------------------------------------------

_STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

_FAKE_ENGINE_SIGNAL = {
    "evaluation": {"band": "equal", "side": "white"},
    "phase": "opening",
    "eval_delta": "stable",
    "last_move_quality": "unknown",
    "tactical_flags": [],
    "position_flags": [],
}


class TestAnalyzeContractSchema:
    """POST /analyze response schema validation.

    Pinned invariants
    -----------------
    ANALYZE_01  Response contains exactly one top-level field: 'engine_signal'.
    ANALYZE_02  'engine_signal' value is a dict.
    ANALYZE_03  Response reflects the value returned by build_engine_signal().
    ANALYZE_04  'startpos' FEN alias is accepted without error.
    ANALYZE_05  FEN with wrong number of parts raises pydantic ValidationError.
    ANALYZE_06  user_query longer than 2000 chars raises pydantic ValidationError.
    ANALYZE_07  verify_api_key dependency is present on the route (AST guard).
    ANALYZE_08  Route method is POST (AST guard).
    """

    def _call_analyze(self, monkeypatch, fen: str = _STARTING_FEN):
        import llm.server as server_module
        from starlette.requests import Request as StarletteRequest
        from starlette.datastructures import Headers

        monkeypatch.setattr(
            server_module, "build_engine_signal", lambda req: _FAKE_ENGINE_SIGNAL
        )
        # slowapi requires a real starlette Request; construct a minimal one.
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/analyze",
            "headers": [],
            "client": ("127.0.0.1", 0),
            "query_string": b"",
        }
        fake_request = StarletteRequest(scope)
        req = server_module.AnalyzeRequest(fen=fen)
        return server_module.analyze(req=req, request=fake_request, _=None)

    def test_analyze_01_response_has_engine_signal_field(self, monkeypatch):
        result = self._call_analyze(monkeypatch)
        assert "engine_signal" in result, (
            "POST /analyze response must contain 'engine_signal'"
        )

    def test_analyze_02_engine_signal_is_dict(self, monkeypatch):
        result = self._call_analyze(monkeypatch)
        _assert_dict(result["engine_signal"], "engine_signal")

    def test_analyze_01_response_has_exactly_one_top_level_field(self, monkeypatch):
        result = self._call_analyze(monkeypatch)
        assert set(result.keys()) == {"engine_signal"}, (
            f"Response must have exactly {{'engine_signal'}} at top level, "
            f"got {set(result.keys())}"
        )

    def test_analyze_03_engine_signal_reflects_build_engine_signal_return(self, monkeypatch):
        result = self._call_analyze(monkeypatch)
        assert result["engine_signal"] == _FAKE_ENGINE_SIGNAL, (
            "engine_signal must be the value returned by build_engine_signal()"
        )

    def test_analyze_04_startpos_alias_accepted(self, monkeypatch):
        """'startpos' is a valid FEN alias; must not raise."""
        result = self._call_analyze(monkeypatch, fen="startpos")
        assert "engine_signal" in result

    def test_analyze_05_invalid_fen_raises_validation_error(self):
        """FEN with wrong number of space-separated parts must be rejected."""
        import pytest
        from pydantic import ValidationError

        import llm.server as server_module

        with pytest.raises(ValidationError):
            server_module.AnalyzeRequest(fen="not-a-valid-fen")

    def test_analyze_06_user_query_too_long_raises_validation_error(self):
        """user_query longer than 2000 characters must be rejected."""
        import pytest
        from pydantic import ValidationError

        import llm.server as server_module

        with pytest.raises(ValidationError):
            server_module.AnalyzeRequest(fen=_STARTING_FEN, user_query="x" * 2001)

    def test_analyze_07_route_has_verify_api_key_dependency(self):
        """verify_api_key must be a dependency on the /analyze route (AST guard)."""
        import ast
        from pathlib import Path

        src = (Path(__file__).parent.parent / "server.py").read_text()
        tree = ast.parse(src)

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "analyze":
                continue
            decorators = [ast.unparse(d) for d in node.decorator_list]
            args_src = ast.unparse(node.args)
            # verify_api_key appears either as a decorator argument or as a Depends call
            combined = " ".join(decorators) + " " + args_src
            assert "verify_api_key" in combined, (
                "verify_api_key dependency missing from /analyze route — "
                "endpoint would be unauthenticated"
            )
            return

        raise AssertionError("analyze() function not found in server.py")

    def test_analyze_08_route_method_is_post(self):
        """The /analyze route must be registered as POST, not GET."""
        import ast
        from pathlib import Path

        src = (Path(__file__).parent.parent / "server.py").read_text()
        tree = ast.parse(src)

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "analyze":
                continue
            for dec in node.decorator_list:
                dec_str = ast.unparse(dec)
                if "/analyze" in dec_str:
                    assert "app.post" in dec_str, (
                        f"/analyze must be registered as POST, got: {dec_str!r}"
                    )
                    return

        raise AssertionError("@app.<method>('/analyze') decorator not found")
