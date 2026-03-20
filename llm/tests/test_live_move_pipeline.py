"""
Unit tests for the per-move live coaching pipeline.

Modules under test
------------------
llm.seca.coach.live_move_pipeline
    LiveMoveReply, generate_live_reply,
    _build_hint

Invariants pinned
-----------------
 1. REPLY_NONNULL:            generate_live_reply always returns a LiveMoveReply.
 2. HINT_NONNULL:             LiveMoveReply.hint is a non-empty string.
 3. ENGINE_SIGNAL_KEYS:       engine_signal has all required top-level keys.
 4. MODE_LIVE_V1:             mode is always "LIVE_V1".
 5. ENGINE_EVAL_IN_HINT:      hint always contains engine evaluation band or type.
 6. MOVE_QUALITY_IS_STR:      move_quality is a string.
 7. ENGINE_SIGNAL_NEVER_FROM_USER: engine_signal never reflects player_id text.
 8. DETERMINISM:              identical inputs → identical LiveMoveReply.
 9. FROZEN:                   LiveMoveReply is immutable (frozen dataclass).
10. BAND_VALUES:              band is one of the four valid strings.
11. FORMAT_MATE_HINT:         mate eval type → "mate" in hint.
12. FORMAT_CP_HINT:           cp eval type → "advantage" or "equal" in hint.
13. PHASE_HINT_PRESENT:       phase hint text appears in the hint.
14. QUALITY_COMMENT_BLUNDER:  "blunder" quality label → blunder comment in hint.
15. QUALITY_COMMENT_BEST:     "best" quality label → best comment in hint.
16. LAYER_NO_RL:              live_move_pipeline.py imports no RL/brain modules.
17. LAYER_NO_SQL:             live_move_pipeline.py imports no sqlalchemy.
18. STARTPOS_FEN:             works correctly with the starting position FEN.
19. MID_FEN:                  works correctly with a mid-game FEN.
20. PLAYER_ID_NOT_IN_SIGNAL:  player_id value is absent from engine_signal.
21. UCI_4_CHARS:              4-char UCI move (e.g. "e2e4") produces a valid reply.
22. UCI_5_CHARS:              5-char UCI move (promotion, e.g. "e7e8q") is accepted.
23. ENGINE_SIGNAL_BAND_TYPE:  evaluation sub-dict has "band" and "type" keys.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from llm.seca.coach.live_move_pipeline import (
    LiveMoveReply,
    generate_live_reply,
    _build_hint,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_VALID_BANDS = {"equal", "small_advantage", "clear_advantage", "decisive_advantage"}
_REQUIRED_ESV_KEYS = {
    "evaluation",
    "eval_delta",
    "last_move_quality",
    "tactical_flags",
    "position_flags",
    "phase",
}

_STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_MID_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
_ENDGAME_FEN = "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1"

_UCI_NORMAL = "e2e4"
_UCI_PROMO = "e7e8q"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_imports(module_path: Path) -> set[str]:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _make_signal(
    eval_type: str = "cp",
    band: str = "equal",
    side: str = "white",
    phase: str = "middlegame",
    move_quality: str = "unknown",
) -> dict:
    return {
        "evaluation": {"type": eval_type, "band": band, "side": side},
        "eval_delta": "stable",
        "last_move_quality": move_quality,
        "tactical_flags": [],
        "position_flags": [],
        "phase": phase,
    }


# ---------------------------------------------------------------------------
# 1–6  Core return-value invariants
# ---------------------------------------------------------------------------


class TestLiveMoveReplyInvariants:

    def test_returns_live_move_reply_instance(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        assert isinstance(result, LiveMoveReply)

    def test_hint_is_non_empty_string(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        assert isinstance(result.hint, str) and result.hint.strip()

    def test_engine_signal_has_all_required_keys(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        missing = _REQUIRED_ESV_KEYS - result.engine_signal.keys()
        assert not missing, f"Missing engine_signal keys: {missing}"

    def test_mode_is_live_v1(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        assert result.mode == "LIVE_V1"

    def test_hint_contains_engine_evaluation_reference(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        band = result.engine_signal["evaluation"]["band"]
        band_word = band.replace("_", " ")
        assert any(
            w in result.hint for w in band_word.split()
        ), f"Hint does not reference evaluation band '{band}': {result.hint!r}"

    def test_move_quality_is_string(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        assert isinstance(result.move_quality, str)


# ---------------------------------------------------------------------------
# 7  Engine signal isolation
# ---------------------------------------------------------------------------


class TestEngineSignalIsolation:

    def test_engine_signal_does_not_contain_player_id(self):
        sentinel = "INJECTION_PROBE_XYZZY"
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL, player_id=sentinel)
        signal_str = str(result.engine_signal)
        assert sentinel not in signal_str, (
            "engine_signal must never reflect player_id: " + signal_str
        )

    def test_engine_signal_band_is_valid(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        band = result.engine_signal["evaluation"]["band"]
        assert band in _VALID_BANDS, f"Unknown band: {band!r}"


# ---------------------------------------------------------------------------
# 8  Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_identical_inputs_produce_identical_output(self):
        r1 = generate_live_reply(_MID_FEN, _UCI_NORMAL, player_id="player1")
        r2 = generate_live_reply(_MID_FEN, _UCI_NORMAL, player_id="player1")
        assert r1.hint == r2.hint
        assert r1.engine_signal == r2.engine_signal
        assert r1.move_quality == r2.move_quality
        assert r1.mode == r2.mode

    def test_different_fens_may_differ(self):
        r1 = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        r2 = generate_live_reply(_MID_FEN, _UCI_NORMAL)
        # Both must be valid; we just confirm no crash and non-empty hints
        assert r1.hint.strip()
        assert r2.hint.strip()


# ---------------------------------------------------------------------------
# 9  Immutability
# ---------------------------------------------------------------------------


class TestDataclassImmutability:

    def test_live_move_reply_is_frozen(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        with pytest.raises((AttributeError, TypeError)):
            result.mode = "MODIFIED"  # type: ignore[misc]

    def test_live_move_reply_hint_is_frozen(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        with pytest.raises((AttributeError, TypeError)):
            result.hint = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 10  Band values
# ---------------------------------------------------------------------------


class TestBandValues:

    def test_starting_fen_band_is_valid(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        assert result.engine_signal["evaluation"]["band"] in _VALID_BANDS

    def test_mid_fen_band_is_valid(self):
        result = generate_live_reply(_MID_FEN, _UCI_NORMAL)
        assert result.engine_signal["evaluation"]["band"] in _VALID_BANDS


# ---------------------------------------------------------------------------
# 11–12  _build_hint formatting
# ---------------------------------------------------------------------------


class TestBuildHintFormatting:

    def test_mate_signal_produces_mate_in_hint(self):
        signal = _make_signal(eval_type="mate", band="decisive_advantage", side="white")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "mate" in hint.lower(), f"Expected 'mate' in hint: {hint!r}"

    def test_cp_equal_produces_equal_in_hint(self):
        signal = _make_signal(eval_type="cp", band="equal", side="black")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "equal" in hint.lower(), f"Expected 'equal' in hint: {hint!r}"

    def test_cp_advantage_produces_advantage_in_hint(self):
        signal = _make_signal(eval_type="cp", band="clear_advantage", side="white")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "advantage" in hint.lower(), f"Expected 'advantage' in hint: {hint!r}"

    def test_hint_is_non_empty_string(self):
        signal = _make_signal()
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert isinstance(hint, str) and hint.strip()


# ---------------------------------------------------------------------------
# 13  Phase hint
# ---------------------------------------------------------------------------


class TestPhaseHintPresent:

    def test_opening_phase_hint_in_hint(self):
        signal = _make_signal(phase="opening")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "develop" in hint.lower() or "centre" in hint.lower(), (
            f"Opening phase hint missing: {hint!r}"
        )

    def test_middlegame_phase_hint_in_hint(self):
        signal = _make_signal(phase="middlegame")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "tactical" in hint.lower() or "activity" in hint.lower(), (
            f"Middlegame phase hint missing: {hint!r}"
        )

    def test_endgame_phase_hint_in_hint(self):
        signal = _make_signal(phase="endgame")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "king" in hint.lower() or "endgame" in hint.lower() or "convert" in hint.lower(), (
            f"Endgame phase hint missing: {hint!r}"
        )


# ---------------------------------------------------------------------------
# 14–15  Move quality comments
# ---------------------------------------------------------------------------


class TestMoveQualityComments:

    def test_blunder_quality_produces_blunder_comment(self):
        signal = _make_signal(move_quality="blunder")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "blunder" in hint.lower(), f"Expected blunder comment: {hint!r}"

    def test_best_quality_produces_best_comment(self):
        signal = _make_signal(move_quality="best")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "best" in hint.lower() or "optimal" in hint.lower(), (
            f"Expected best-move comment: {hint!r}"
        )

    def test_unknown_quality_produces_no_quality_comment(self):
        signal = _make_signal(move_quality="unknown")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        # "unknown" should not appear as a quality label in the hint
        assert "unknown" not in hint.lower(), f"'unknown' leaked into hint: {hint!r}"

    def test_mistake_quality_produces_mistake_comment(self):
        signal = _make_signal(move_quality="mistake")
        hint = _build_hint(_UCI_NORMAL, signal, "")
        assert "mistake" in hint.lower(), f"Expected mistake comment: {hint!r}"


# ---------------------------------------------------------------------------
# 16–17  Layer boundaries
# ---------------------------------------------------------------------------


class TestLayerBoundary:

    _FORBIDDEN_RL = ("rl", "reinforcement", "brain", "policy", "reward")
    _FORBIDDEN_SQL = ("sqlalchemy",)

    def _imports(self) -> set[str]:
        path = PROJECT_ROOT / "llm" / "seca" / "coach" / "live_move_pipeline.py"
        assert path.exists(), "live_move_pipeline.py not found"
        return _get_imports(path)

    def test_no_rl_imports(self):
        imports = self._imports()
        violations = {i for i in imports if any(p in i.lower() for p in self._FORBIDDEN_RL)}
        assert not violations, f"live_move_pipeline.py imports RL modules: {violations}"

    def test_no_sqlalchemy_imports(self):
        imports = self._imports()
        violations = {i for i in imports if any(p in i for p in self._FORBIDDEN_SQL)}
        assert not violations, f"live_move_pipeline.py imports SQLAlchemy: {violations}"


# ---------------------------------------------------------------------------
# 18–19  FEN variety
# ---------------------------------------------------------------------------


class TestFenVariety:

    def test_starting_position_fen(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        assert isinstance(result, LiveMoveReply)
        assert result.hint.strip()

    def test_mid_game_fen(self):
        result = generate_live_reply(_MID_FEN, _UCI_NORMAL)
        assert isinstance(result, LiveMoveReply)
        assert result.hint.strip()

    def test_endgame_fen(self):
        result = generate_live_reply(_ENDGAME_FEN, _UCI_NORMAL)
        assert isinstance(result, LiveMoveReply)
        assert result.hint.strip()


# ---------------------------------------------------------------------------
# 20  player_id isolation
# ---------------------------------------------------------------------------


class TestPlayerIdIsolation:

    def test_player_id_not_in_engine_signal(self):
        player_id = "unique_player_id_abc123"
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL, player_id=player_id)
        assert player_id not in str(result.engine_signal)

    def test_different_player_ids_same_signal(self):
        r1 = generate_live_reply(_STARTING_FEN, _UCI_NORMAL, player_id="alice")
        r2 = generate_live_reply(_STARTING_FEN, _UCI_NORMAL, player_id="bob")
        # Engine signal must be identical regardless of player_id
        assert r1.engine_signal == r2.engine_signal


# ---------------------------------------------------------------------------
# 21–22  UCI move length variants
# ---------------------------------------------------------------------------


class TestUciMoveVariants:

    def test_4_char_uci_accepted(self):
        result = generate_live_reply(_STARTING_FEN, "e2e4")
        assert result.hint.strip()

    def test_5_char_uci_promotion_accepted(self):
        result = generate_live_reply(_STARTING_FEN, "e7e8q")
        assert result.hint.strip()


# ---------------------------------------------------------------------------
# 23  engine_signal sub-dict structure
# ---------------------------------------------------------------------------


class TestEngineSignalSubDict:

    def test_evaluation_has_band_and_type(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        ev = result.engine_signal.get("evaluation", {})
        assert "band" in ev, "evaluation missing 'band'"
        assert "type" in ev, "evaluation missing 'type'"

    def test_evaluation_type_is_cp_or_mate(self):
        result = generate_live_reply(_STARTING_FEN, _UCI_NORMAL)
        ev_type = result.engine_signal["evaluation"]["type"]
        assert ev_type in ("cp", "mate"), f"Unexpected eval type: {ev_type!r}"
