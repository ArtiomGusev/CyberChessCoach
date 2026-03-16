"""
Unit tests for the long-form chat coaching pipeline.

Modules under test
------------------
llm.seca.coach.chat_pipeline
    ChatTurn, ChatReply, generate_chat_reply,
    _format_engine_context, _build_context_block

Invariants pinned
-----------------
 1. REPLY_NONNULL:          generate_chat_reply always returns a ChatReply.
 2. REPLY_STR:              ChatReply.reply is a non-empty string.
 3. ENGINE_SIGNAL_KEYS:     engine_signal has all required top-level keys.
 4. MODE_CHAT_V1:           mode is always "CHAT_V1".
 5. ENGINE_EVAL_IN_REPLY:   reply always contains engine evaluation band or type.
 6. EMPTY_MESSAGES:         empty history → reply still references eval.
 7. SINGLE_USER_TURN:       one user message → query addressed in reply.
 8. MULTI_TURN_HISTORY:     prior user turn referenced when history > 1 turn.
 9. PLAYER_PROFILE:         player profile fields appear in context block.
10. PAST_MISTAKES:          past mistakes appear in context block.
11. FORMAT_ENGINE_CP:       cp eval type → "advantage" phrasing present.
12. FORMAT_ENGINE_MATE:     mate eval type → "mate" phrasing present.
13. CONTEXT_NO_PROFILE:     context block with no profile → no crash.
14. ENGINE_SIGNAL_NEVER_FROM_USER: engine_signal never contains user text.
15. DETERMINISM:            identical inputs → identical ChatReply.
16. CHAT_TURN_FROZEN:       ChatTurn is immutable (frozen dataclass).
17. CHAT_REPLY_FROZEN:      ChatReply is immutable (frozen dataclass).
18. LAYER_BOUNDARY:         chat_pipeline.py imports no RL / brain modules.
19. LAYER_BOUNDARY:         chat_pipeline.py imports no sqlalchemy.
20. ENGINE_SIGNAL_BAND_VALUES: band is one of the four valid strings.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from llm.seca.coach.chat_pipeline import (
    ChatTurn,
    ChatReply,
    generate_chat_reply,
    _format_engine_context,
    _build_context_block,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_VALID_BANDS = {"equal", "small_advantage", "clear_advantage", "decisive_advantage"}
_REQUIRED_ESV_KEYS = {"evaluation", "eval_delta", "last_move_quality",
                      "tactical_flags", "position_flags", "phase"}

_STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_MID_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"


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


def _make_turns(*pairs: tuple[str, str]) -> list[ChatTurn]:
    return [ChatTurn(role=r, content=c) for r, c in pairs]


# ---------------------------------------------------------------------------
# 1–5  Core return-value invariants
# ---------------------------------------------------------------------------

class TestChatReplyInvariants:

    def test_returns_chat_reply_instance(self):
        result = generate_chat_reply(_STARTING_FEN, [])
        assert isinstance(result, ChatReply)

    def test_reply_is_non_empty_string(self):
        result = generate_chat_reply(_STARTING_FEN, [])
        assert isinstance(result.reply, str) and result.reply.strip()

    def test_engine_signal_has_all_required_keys(self):
        result = generate_chat_reply(_STARTING_FEN, [])
        missing = _REQUIRED_ESV_KEYS - result.engine_signal.keys()
        assert not missing, f"Missing engine_signal keys: {missing}"

    def test_mode_is_chat_v1(self):
        result = generate_chat_reply(_STARTING_FEN, [])
        assert result.mode == "CHAT_V1"

    def test_reply_contains_engine_evaluation_reference(self):
        result = generate_chat_reply(_STARTING_FEN, [])
        band = result.engine_signal["evaluation"]["band"]
        band_word = band.replace("_", " ")
        # Any part of the band label should appear in the reply
        assert any(w in result.reply for w in band_word.split()), (
            f"Reply does not reference evaluation band '{band}': {result.reply!r}"
        )


# ---------------------------------------------------------------------------
# 6–8  Message history handling
# ---------------------------------------------------------------------------

class TestMessageHistoryHandling:

    def test_empty_history_still_produces_reply(self):
        result = generate_chat_reply(_MID_FEN, [])
        assert result.reply.strip()

    def test_single_user_turn_query_addressed(self):
        turns = _make_turns(("user", "What is the best plan here?"))
        result = generate_chat_reply(_STARTING_FEN, turns)
        # The user query or a reference to it should appear in the reply
        assert "best plan" in result.reply or "question" in result.reply.lower()

    def test_multi_turn_history_references_prior_question(self):
        turns = _make_turns(
            ("user", "How should I develop my pieces?"),
            ("assistant", "Focus on knights and bishops first."),
            ("user", "What about the centre?"),
        )
        result = generate_chat_reply(_STARTING_FEN, turns)
        # Prior user question should be referenced
        assert "develop" in result.reply.lower() or "earlier" in result.reply.lower() or \
               "Following" in result.reply


# ---------------------------------------------------------------------------
# 9–10  Player profile & past mistakes
# ---------------------------------------------------------------------------

class TestPlayerContext:

    def test_player_profile_skill_appears_in_context(self):
        profile = {"skill_estimate": "intermediate", "common_mistakes": [], "strengths": []}
        turns = _make_turns(("user", "Analyse this position."))
        result = generate_chat_reply(_STARTING_FEN, turns, player_profile=profile)
        assert "intermediate" in result.reply

    def test_player_profile_mistakes_appear_in_context(self):
        profile = {
            "skill_estimate": "beginner",
            "common_mistakes": [{"tag": "tactical_vision", "count": 5}],
            "strengths": ["endgame"],
        }
        turns = _make_turns(("user", "What should I work on?"))
        result = generate_chat_reply(_STARTING_FEN, turns, player_profile=profile)
        assert "tactical_vision" in result.reply

    def test_past_mistakes_appear_in_reply(self):
        turns = _make_turns(("user", "Any training suggestions?"))
        result = generate_chat_reply(
            _STARTING_FEN, turns,
            past_mistakes=["opening_preparation", "endgame_technique"],
        )
        assert "opening_preparation" in result.reply or "opening" in result.reply.lower()

    def test_no_profile_does_not_crash(self):
        result = generate_chat_reply(_STARTING_FEN, [], player_profile=None, past_mistakes=None)
        assert result.reply.strip()


# ---------------------------------------------------------------------------
# 11–12  _format_engine_context
# ---------------------------------------------------------------------------

class TestFormatEngineContext:

    def _cp_signal(self, band: str = "equal", side: str = "white") -> dict:
        return {
            "evaluation": {"type": "cp", "band": band, "side": side},
            "eval_delta": "stable",
            "last_move_quality": "unknown",
            "tactical_flags": [],
            "position_flags": [],
            "phase": "middlegame",
        }

    def _mate_signal(self, side: str = "white") -> dict:
        return {
            "evaluation": {"type": "mate", "band": "decisive_advantage", "side": side},
            "eval_delta": "increase",
            "last_move_quality": "unknown",
            "tactical_flags": [],
            "position_flags": [],
            "phase": "endgame",
        }

    def test_cp_eval_mentions_advantage_or_equal(self):
        ctx = _format_engine_context(self._cp_signal("clear_advantage", "white"))
        assert "advantage" in ctx.lower() or "equal" in ctx.lower()

    def test_cp_eval_equal_band(self):
        ctx = _format_engine_context(self._cp_signal("equal", "black"))
        assert "equal" in ctx.lower()

    def test_mate_eval_mentions_mate(self):
        ctx = _format_engine_context(self._mate_signal("black"))
        assert "mate" in ctx.lower()

    def test_phase_included_in_context(self):
        ctx = _format_engine_context(self._cp_signal())
        assert "middlegame" in ctx.lower() or "opening" in ctx.lower() or "endgame" in ctx.lower()

    def test_delta_hint_present(self):
        signal = self._cp_signal()
        signal["eval_delta"] = "decrease"
        ctx = _format_engine_context(signal)
        assert "deteriorated" in ctx.lower() or "decrease" in ctx.lower()


# ---------------------------------------------------------------------------
# 13  _build_context_block
# ---------------------------------------------------------------------------

class TestBuildContextBlock:

    def _neutral_signal(self) -> dict:
        from llm.rag.engine_signal.extract_engine_signal import extract_engine_signal
        return extract_engine_signal({}, fen=_STARTING_FEN)

    def test_no_profile_returns_engine_context_only(self):
        block = _build_context_block(self._neutral_signal(), None, None)
        assert isinstance(block, str) and block.strip()

    def test_full_profile_adds_skill_and_mistakes(self):
        profile = {
            "skill_estimate": "advanced",
            "common_mistakes": [{"tag": "endgame_technique", "count": 3}],
            "strengths": ["tactics"],
        }
        block = _build_context_block(self._neutral_signal(), profile, ["opening_preparation"])
        assert "advanced" in block
        assert "endgame_technique" in block
        assert "opening_preparation" in block


# ---------------------------------------------------------------------------
# 14  Engine signal is never user-sourced
# ---------------------------------------------------------------------------

class TestEngineSignalIsolation:

    def test_engine_signal_does_not_contain_user_text(self):
        sentinel = "INJECTION_PROBE_12345"
        turns = _make_turns(("user", sentinel))
        result = generate_chat_reply(_STARTING_FEN, turns)
        signal_str = str(result.engine_signal)
        assert sentinel not in signal_str, (
            "engine_signal must never reflect user-supplied content"
        )

    def test_engine_signal_band_is_valid(self):
        result = generate_chat_reply(_STARTING_FEN, [])
        band = result.engine_signal["evaluation"]["band"]
        assert band in _VALID_BANDS, f"Unknown band: {band!r}"


# ---------------------------------------------------------------------------
# 15  Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_identical_inputs_produce_identical_output(self):
        turns = _make_turns(
            ("user", "Should I castle?"),
            ("assistant", "King safety is important."),
            ("user", "Which side?"),
        )
        r1 = generate_chat_reply(_MID_FEN, turns)
        r2 = generate_chat_reply(_MID_FEN, turns)
        assert r1.reply == r2.reply
        assert r1.engine_signal == r2.engine_signal
        assert r1.mode == r2.mode


# ---------------------------------------------------------------------------
# 16–17  Immutability
# ---------------------------------------------------------------------------

class TestDataclassImmutability:

    def test_chat_turn_is_frozen(self):
        turn = ChatTurn(role="user", content="test")
        with pytest.raises((AttributeError, TypeError)):
            turn.role = "assistant"  # type: ignore[misc]

    def test_chat_reply_is_frozen(self):
        result = generate_chat_reply(_STARTING_FEN, [])
        with pytest.raises((AttributeError, TypeError)):
            result.mode = "MODIFIED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 18–19  Layer boundary
# ---------------------------------------------------------------------------

class TestLayerBoundary:

    _FORBIDDEN_RL = ("rl", "reinforcement", "brain", "policy", "reward")
    _FORBIDDEN_SQL = ("sqlalchemy",)

    def _imports(self) -> set[str]:
        path = PROJECT_ROOT / "llm" / "seca" / "coach" / "chat_pipeline.py"
        assert path.exists(), "chat_pipeline.py not found"
        return _get_imports(path)

    def test_no_rl_imports(self):
        imports = self._imports()
        violations = {i for i in imports if any(p in i.lower() for p in self._FORBIDDEN_RL)}
        assert not violations, f"chat_pipeline.py imports RL modules: {violations}"

    def test_no_sqlalchemy_imports(self):
        imports = self._imports()
        violations = {i for i in imports if any(p in i for p in self._FORBIDDEN_SQL)}
        assert not violations, f"chat_pipeline.py imports SQLAlchemy: {violations}"
