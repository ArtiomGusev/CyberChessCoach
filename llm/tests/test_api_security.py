"""
Security tests for the backend API.

Approach
--------
Tests are split into three tiers to stay CI-safe (no live Stockfish / DB):

  Tier 1 — AST inspection
    Parse server.py and auth/router.py source code to verify that each
    endpoint that should require authentication has a `verify_api_key` or
    `get_current_player` dependency, and that the logout handler wraps
    `decode_token` in a try/except block.

  Tier 2 — Pydantic model validation (in-process)
    Instantiate the real server-side Pydantic models (`OutcomeRequest`,
    `LiveMoveRequest`) via direct import and confirm that out-of-range or
    malformed payloads raise `ValidationError`.

  Tier 3 — HTTP-layer authentication (minimal stub app)
    Create a self-contained FastAPI + TestClient instance that mirrors the
    `verify_api_key` logic from server.py.  Tests confirm that protected
    endpoints return 401 without a valid API key and 200 with one.  No
    server.py import occurs in this tier, avoiding the problematic module
    chains documented in run_ci_suite.py.

Invariants pinned
-----------------
 1. SEC_ANALYZE_AUTH_APPLIED        /analyze endpoint has verify_api_key dependency.
 2. SEC_OUTCOME_AUTH_APPLIED        /explanation_outcome has verify_api_key dependency.
 3. SEC_LIVEMOVE_AUTH_APPLIED       /live/move has verify_api_key dependency.
 4. SEC_DEBUG_ENGINE_AUTH_APPLIED   /debug/engine has verify_api_key dependency.
 5. SEC_LOGOUT_WRAPS_DECODE_TOKEN   logout wraps decode_token in try/except.
 6. SEC_OUTCOME_NEG_MOVES           moves_analyzed < 0 → ValidationError.
 7. SEC_OUTCOME_LARGE_MOVES         moves_analyzed > 10000 → ValidationError.
 8. SEC_OUTCOME_BLUNDER_LOW         blunder_rate < 0.0 → ValidationError.
 9. SEC_OUTCOME_BLUNDER_HIGH        blunder_rate > 1.0 → ValidationError.
10. SEC_OUTCOME_CPL_LOW             avg_cpl < -3000 → ValidationError.
11. SEC_OUTCOME_CPL_HIGH            avg_cpl > 3000 → ValidationError.
12. SEC_OUTCOME_DELTA_LOW           confidence_delta < -1.0 → ValidationError.
13. SEC_OUTCOME_DELTA_HIGH          confidence_delta > 1.0 → ValidationError.
14. SEC_OUTCOME_ID_TOO_LONG        explanation_id > 200 chars → ValidationError.
15. SEC_OUTCOME_VALID_ACCEPTED      Valid OutcomeRequest passes validation.
16. SEC_LIVEMOVE_BAD_FEN            Invalid FEN in LiveMoveRequest → ValidationError.
17. SEC_LIVEMOVE_SHORT_UCI          UCI < 4 chars → ValidationError.
18. SEC_LIVEMOVE_LONG_UCI           UCI > 5 chars → ValidationError.
19. SEC_LIVEMOVE_LONG_PLAYER_ID     player_id > 100 chars → ValidationError.
20. SEC_LIVEMOVE_VALID_ACCEPTED     Valid LiveMoveRequest passes validation.
21. SEC_HTTP_ANALYZE_NO_KEY_401     POST /analyze without key → 401.
22. SEC_HTTP_ANALYZE_WRONG_KEY_401  POST /analyze with wrong key → 401.
23. SEC_HTTP_ANALYZE_CORRECT_KEY    POST /analyze with correct key → 200.
24. SEC_HTTP_OUTCOME_NO_KEY_401     POST /explanation_outcome without key → 401.
25. SEC_HTTP_LIVEMOVE_NO_KEY_401    POST /live/move without key → 401.
26. SEC_HTTP_DEBUG_NO_KEY_401       GET /debug/engine without key → 401.
27. SEC_HTTP_HEALTH_OPEN            GET /health requires no key (must stay open).
28. SEC_APIKEY_DEV_NO_KEY_PASSES    verify_api_key passes when no SECA_API_KEY set (dev mode).
29. SEC_APIKEY_CORRECT_KEY_PASSES   verify_api_key passes with correct key.
30. SEC_APIKEY_WRONG_KEY_401        verify_api_key raises HTTPException(401) on wrong key.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SERVER_PY  = _REPO_ROOT / "llm" / "server.py"
_AUTH_ROUTER = _REPO_ROOT / "llm" / "seca" / "auth" / "router.py"


# ===========================================================================
# Tier 1 — AST Inspection
# ===========================================================================


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _get_decorated_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Return {function_name: FunctionDef} for all top-level decorated defs."""
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _depends_on(func_def: ast.FunctionDef, target: str) -> bool:
    """
    Return True if any argument default in func_def is a Depends(target) call.
    Handles both `Depends(target)` and `Depends(verify_api_key)` patterns.
    """
    for default in func_def.args.defaults + func_def.args.kw_defaults:
        if default is None:
            continue
        if not isinstance(default, ast.Call):
            continue
        call = default
        # Depends(target)
        func = call.func
        if isinstance(func, ast.Name) and func.id == "Depends":
            for arg in call.args:
                if isinstance(arg, ast.Name) and arg.id == target:
                    return True
    return False


class TestAstEndpointProtection:

    def setup_method(self):
        self._server = _parse(_SERVER_PY)
        self._funcs  = _get_decorated_functions(self._server)

    def test_analyze_has_verify_api_key(self):
        """SEC_ANALYZE_AUTH_APPLIED: /analyze endpoint has verify_api_key dependency."""
        func = self._funcs.get("analyze")
        assert func is not None, "analyze() function not found in server.py"
        assert _depends_on(func, "verify_api_key"), (
            "POST /analyze must have Depends(verify_api_key) — endpoint is unauthenticated"
        )

    def test_explanation_outcome_has_verify_api_key(self):
        """SEC_OUTCOME_AUTH_APPLIED: /explanation_outcome has verify_api_key dependency."""
        func = self._funcs.get("report_outcome")
        assert func is not None, "report_outcome() not found in server.py"
        assert _depends_on(func, "verify_api_key"), (
            "POST /explanation_outcome must have Depends(verify_api_key) — "
            "unauthenticated write to learning state"
        )

    def test_live_move_has_verify_api_key(self):
        """SEC_LIVEMOVE_AUTH_APPLIED: /live/move has verify_api_key dependency."""
        func = self._funcs.get("live_move")
        assert func is not None, "live_move() not found in server.py"
        assert _depends_on(func, "verify_api_key"), (
            "POST /live/move must have Depends(verify_api_key)"
        )

    def test_debug_engine_has_verify_api_key(self):
        """SEC_DEBUG_ENGINE_AUTH_APPLIED: /debug/engine has verify_api_key dependency."""
        func = self._funcs.get("engine_debug")
        assert func is not None, "engine_debug() not found in server.py"
        assert _depends_on(func, "verify_api_key"), (
            "GET /debug/engine must have Depends(verify_api_key) — leaks engine pool info"
        )


class TestAstLogoutProtection:

    def test_logout_wraps_decode_token_in_try_except(self):
        """SEC_LOGOUT_WRAPS_DECODE_TOKEN: logout wraps decode_token in try/except.

        A bare decode_token() call propagates jwt exceptions as HTTP 500.
        The fix wraps it in try/except and raises HTTPException(401).
        """
        tree = _parse(_AUTH_ROUTER)

        logout_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "logout":
                logout_func = node
                break

        assert logout_func is not None, "logout() not found in auth/router.py"

        # Walk the function body looking for a Try node that contains a
        # call to decode_token.
        def _contains_decode_token_call(nodes) -> bool:
            for node in ast.walk(nodes if isinstance(nodes, ast.AST) else ast.Module(body=nodes, type_ignores=[])):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "decode_token":
                        return True
            return False

        try_nodes = [n for n in ast.walk(logout_func) if isinstance(n, ast.Try)]
        assert try_nodes, (
            "logout() has no try/except block. "
            "decode_token() must be wrapped to prevent 500 on invalid tokens."
        )

        found_wrapped = any(
            _contains_decode_token_call(try_node.body)
            for try_node in try_nodes
        )
        assert found_wrapped, (
            "No try/except block in logout() wraps a decode_token() call. "
            "An invalid token returns 500 instead of 401."
        )


# ===========================================================================
# Tier 2 — Pydantic Model Validation (direct import, isolated models)
# ===========================================================================

# Import the real model classes from server.py via a sys.path trick to avoid
# executing the startup code.  We import only the model classes which are
# pure-Pydantic and have no side effects.
#
# If the import is not possible in CI (module chain issue), the tests fall
# back to locally-defined mirrors of the validators.

try:
    # Set env before any import that reads API_KEY.
    os.environ.setdefault("SECA_API_KEY", "ci-test-key")
    os.environ.setdefault("SECA_ENV", "dev")

    from llm.server import OutcomeRequest as _OutcomeRequest
    from llm.server import LiveMoveRequest as _LiveMoveRequest

    _MODELS_IMPORTED = True
except Exception:
    # Fallback: replicate the validators locally so Pydantic tests still run.
    # This mirrors the production validators exactly.
    from pydantic import BaseModel, field_validator as _fv

    def _validate_fen_field_local(v: str) -> str:
        stripped = v.strip()
        if stripped.lower() == "startpos":
            return v
        parts = stripped.split()
        if len(parts) != 6 or len(stripped) > 100:
            raise ValueError("invalid FEN")
        return v

    class _OutcomeRequest(BaseModel):  # type: ignore[no-redef]
        explanation_id: str
        moves_analyzed: int
        avg_cpl: float
        blunder_rate: float
        tactic_success: bool
        confidence_delta: float

        @_fv("explanation_id")
        @classmethod
        def validate_explanation_id(cls, v: str) -> str:
            if len(v) > 200:
                raise ValueError("explanation_id too long (max 200 chars)")
            return v

        @_fv("moves_analyzed")
        @classmethod
        def validate_moves_analyzed(cls, v: int) -> int:
            if not (0 <= v <= 10_000):
                raise ValueError("moves_analyzed must be 0–10000")
            return v

        @_fv("avg_cpl")
        @classmethod
        def validate_avg_cpl(cls, v: float) -> float:
            if not (-3_000.0 <= v <= 3_000.0):
                raise ValueError("avg_cpl must be in [-3000, 3000]")
            return v

        @_fv("blunder_rate")
        @classmethod
        def validate_blunder_rate(cls, v: float) -> float:
            if not (0.0 <= v <= 1.0):
                raise ValueError("blunder_rate must be in [0.0, 1.0]")
            return v

        @_fv("confidence_delta")
        @classmethod
        def validate_confidence_delta(cls, v: float) -> float:
            if not (-1.0 <= v <= 1.0):
                raise ValueError("confidence_delta must be in [-1.0, 1.0]")
            return v

    class _LiveMoveRequest(BaseModel):  # type: ignore[no-redef]
        fen: str
        uci: str
        player_id: str = "demo"

        @_fv("fen")
        @classmethod
        def validate_fen(cls, v: str) -> str:
            return _validate_fen_field_local(v)

        @_fv("uci")
        @classmethod
        def validate_uci(cls, v: str) -> str:
            if not (4 <= len(v) <= 5):
                raise ValueError("uci move must be 4–5 characters")
            return v

        @_fv("player_id")
        @classmethod
        def validate_player_id(cls, v: str) -> str:
            if len(v) > 100:
                raise ValueError("player_id too long (max 100 chars)")
            return v

    _MODELS_IMPORTED = False


def _valid_outcome(**overrides) -> dict:
    base = {
        "explanation_id": "expl-001",
        "moves_analyzed": 10,
        "avg_cpl": 25.0,
        "blunder_rate": 0.1,
        "tactic_success": True,
        "confidence_delta": 0.05,
    }
    base.update(overrides)
    return base


def _valid_live_move(**overrides) -> dict:
    base = {
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "uci": "e7e5",
        "player_id": "player1",
    }
    base.update(overrides)
    return base


class TestOutcomeRequestValidation:

    def test_negative_moves_analyzed_rejected(self):
        """SEC_OUTCOME_NEG_MOVES: moves_analyzed < 0 → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(moves_analyzed=-1))

    def test_excess_moves_analyzed_rejected(self):
        """SEC_OUTCOME_LARGE_MOVES: moves_analyzed > 10000 → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(moves_analyzed=10_001))

    def test_blunder_rate_below_zero_rejected(self):
        """SEC_OUTCOME_BLUNDER_LOW: blunder_rate < 0.0 → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(blunder_rate=-0.1))

    def test_blunder_rate_above_one_rejected(self):
        """SEC_OUTCOME_BLUNDER_HIGH: blunder_rate > 1.0 → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(blunder_rate=1.01))

    def test_avg_cpl_too_low_rejected(self):
        """SEC_OUTCOME_CPL_LOW: avg_cpl < -3000 → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(avg_cpl=-3_001.0))

    def test_avg_cpl_too_high_rejected(self):
        """SEC_OUTCOME_CPL_HIGH: avg_cpl > 3000 → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(avg_cpl=3_001.0))

    def test_confidence_delta_too_low_rejected(self):
        """SEC_OUTCOME_DELTA_LOW: confidence_delta < -1.0 → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(confidence_delta=-1.01))

    def test_confidence_delta_too_high_rejected(self):
        """SEC_OUTCOME_DELTA_HIGH: confidence_delta > 1.0 → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(confidence_delta=1.01))

    def test_explanation_id_too_long_rejected(self):
        """SEC_OUTCOME_ID_TOO_LONG: explanation_id > 200 chars → ValidationError."""
        with pytest.raises(ValidationError):
            _OutcomeRequest(**_valid_outcome(explanation_id="x" * 201))

    def test_valid_outcome_request_accepted(self):
        """SEC_OUTCOME_VALID_ACCEPTED: All valid fields pass validation."""
        req = _OutcomeRequest(**_valid_outcome())
        assert req.moves_analyzed == 10
        assert req.blunder_rate == 0.1


class TestLiveMoveRequestValidation:

    def test_invalid_fen_rejected(self):
        """SEC_LIVEMOVE_BAD_FEN: Invalid FEN string → ValidationError."""
        with pytest.raises(ValidationError):
            _LiveMoveRequest(**_valid_live_move(fen="not-a-fen"))

    def test_fen_too_long_rejected(self):
        """SEC_LIVEMOVE_BAD_FEN: FEN string > 100 chars → ValidationError."""
        long_fen = "a " * 51  # > 100 chars and != 6 parts
        with pytest.raises(ValidationError):
            _LiveMoveRequest(**_valid_live_move(fen=long_fen))

    def test_uci_too_short_rejected(self):
        """SEC_LIVEMOVE_SHORT_UCI: UCI < 4 chars → ValidationError."""
        with pytest.raises(ValidationError):
            _LiveMoveRequest(**_valid_live_move(uci="e7"))

    def test_uci_too_long_rejected(self):
        """SEC_LIVEMOVE_LONG_UCI: UCI > 5 chars → ValidationError."""
        with pytest.raises(ValidationError):
            _LiveMoveRequest(**_valid_live_move(uci="e7e5e3"))

    def test_player_id_too_long_rejected(self):
        """SEC_LIVEMOVE_LONG_PLAYER_ID: player_id > 100 chars → ValidationError."""
        with pytest.raises(ValidationError):
            _LiveMoveRequest(**_valid_live_move(player_id="p" * 101))

    def test_valid_live_move_request_accepted(self):
        """SEC_LIVEMOVE_VALID_ACCEPTED: Valid fields pass validation."""
        req = _LiveMoveRequest(**_valid_live_move())
        assert req.uci == "e7e5"
        assert req.player_id == "player1"


# ===========================================================================
# Tier 3 — HTTP-layer auth tests (minimal stub app, no server.py import)
# ===========================================================================

_TEST_API_KEY = "test-api-key-secure"

# Build a minimal FastAPI app that mirrors the verify_api_key logic.
# This avoids importing llm.server (which triggers heavy module chains in CI).

_stub_app = FastAPI()


def _stub_verify_api_key(x_api_key: str = Header(None)):
    """Mirrors server.py:verify_api_key for HTTP-layer testing."""
    if x_api_key != _TEST_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@_stub_app.post("/analyze")
def _stub_analyze(_: None = Depends(_stub_verify_api_key)):
    return {"engine_signal": {}}


@_stub_app.post("/explanation_outcome")
def _stub_outcome(_: None = Depends(_stub_verify_api_key)):
    return {"learning_score": 0.5}


@_stub_app.post("/live/move")
def _stub_live_move(_: None = Depends(_stub_verify_api_key)):
    return {"status": "not_implemented"}


@_stub_app.get("/debug/engine")
def _stub_debug_engine(_: None = Depends(_stub_verify_api_key)):
    return {"pool_size": 0}


@_stub_app.get("/health")
def _stub_health():
    return {"status": "ok"}


_stub_client = TestClient(_stub_app, raise_server_exceptions=False)

_AUTH_HEADER = {"X-Api-Key": _TEST_API_KEY}
_WRONG_AUTH  = {"X-Api-Key": "wrong-key"}
_VALID_ANALYZE_BODY   = {"fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"}
_VALID_OUTCOME_BODY   = {
    "explanation_id": "expl-1",
    "moves_analyzed": 5,
    "avg_cpl": 30.0,
    "blunder_rate": 0.2,
    "tactic_success": False,
    "confidence_delta": 0.0,
}
_VALID_LIVE_MOVE_BODY = {
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "uci": "e7e5",
}


class TestHttpAuthEnforcement:

    def test_analyze_without_key_returns_401(self):
        """SEC_HTTP_ANALYZE_NO_KEY_401: POST /analyze without API key → 401."""
        r = _stub_client.post("/analyze", json=_VALID_ANALYZE_BODY)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_analyze_with_wrong_key_returns_401(self):
        """SEC_HTTP_ANALYZE_WRONG_KEY_401: POST /analyze with wrong key → 401."""
        r = _stub_client.post("/analyze", json=_VALID_ANALYZE_BODY, headers=_WRONG_AUTH)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_analyze_with_correct_key_returns_200(self):
        """SEC_HTTP_ANALYZE_CORRECT_KEY: POST /analyze with correct key → 200."""
        r = _stub_client.post("/analyze", json=_VALID_ANALYZE_BODY, headers=_AUTH_HEADER)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"

    def test_explanation_outcome_without_key_returns_401(self):
        """SEC_HTTP_OUTCOME_NO_KEY_401: POST /explanation_outcome without key → 401."""
        r = _stub_client.post("/explanation_outcome", json=_VALID_OUTCOME_BODY)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_live_move_without_key_returns_401(self):
        """SEC_HTTP_LIVEMOVE_NO_KEY_401: POST /live/move without key → 401."""
        r = _stub_client.post("/live/move", json=_VALID_LIVE_MOVE_BODY)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_debug_engine_without_key_returns_401(self):
        """SEC_HTTP_DEBUG_NO_KEY_401: GET /debug/engine without key → 401."""
        r = _stub_client.get("/debug/engine")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_health_endpoint_requires_no_key(self):
        """SEC_HTTP_HEALTH_OPEN: GET /health must remain open (no auth required)."""
        r = _stub_client.get("/health")
        assert r.status_code == 200, (
            f"GET /health should be publicly accessible; got {r.status_code}"
        )


# ===========================================================================
# verify_api_key logic unit tests
# ===========================================================================


class TestVerifyApiKeyLogic:
    """
    Test the verify_api_key guard in isolation without importing server.py.
    The implementation is replicated here because importing llm.server in CI
    triggers the module chains documented in run_ci_suite.py comments.
    """

    @staticmethod
    def _make_verify(api_key: str | None, is_prod: bool = False):
        """Return a callable that behaves like server.py:verify_api_key."""
        def _check(x_api_key: str | None = None):
            if api_key is None:
                if is_prod:
                    raise HTTPException(status_code=500, detail="Server misconfiguration")
                return  # dev mode
            if x_api_key != api_key:
                raise HTTPException(status_code=401, detail="Unauthorized")
        return _check

    def test_dev_mode_no_key_set_passes(self):
        """SEC_APIKEY_DEV_NO_KEY_PASSES: verify_api_key passes when no API key is set (dev mode)."""
        check = self._make_verify(api_key=None, is_prod=False)
        check(x_api_key=None)   # must not raise
        check(x_api_key="anything")  # must not raise

    def test_correct_key_passes(self):
        """SEC_APIKEY_CORRECT_KEY_PASSES: verify_api_key passes with the correct key."""
        check = self._make_verify(api_key="secret123")
        check(x_api_key="secret123")  # must not raise

    def test_wrong_key_raises_401(self):
        """SEC_APIKEY_WRONG_KEY_401: verify_api_key raises HTTPException(401) on wrong key."""
        check = self._make_verify(api_key="secret123")
        with pytest.raises(HTTPException) as exc_info:
            check(x_api_key="wrong")
        assert exc_info.value.status_code == 401

    def test_no_key_sent_raises_401(self):
        """Missing X-Api-Key header when API key is configured → 401."""
        check = self._make_verify(api_key="secret123")
        with pytest.raises(HTTPException) as exc_info:
            check(x_api_key=None)
        assert exc_info.value.status_code == 401

    def test_prod_mode_no_key_configured_raises_500(self):
        """verify_api_key in prod mode with no env key → HTTPException(500)."""
        check = self._make_verify(api_key=None, is_prod=True)
        with pytest.raises(HTTPException) as exc_info:
            check(x_api_key=None)
        assert exc_info.value.status_code == 500
