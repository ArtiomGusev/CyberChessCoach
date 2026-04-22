"""
Long-form chat coaching pipeline — deterministic, no RL.

Produces a context-aware coaching reply for a multi-turn chess conversation.

Architecture
------------
Inputs:
    fen            Current board position (FEN string).
    messages       List of ChatTurn(role, content) — full conversation history
                   including the latest user message.
    player_profile Optional player context (skill_estimate, common_mistakes,
                   strengths) from the SECA player model.
    past_mistakes  Optional list of MistakeCategory strings from the analytics
                   layer (e.g. ["tactical_vision", "endgame_technique"]).

Processing:
    1. Extract engine signal from the FEN via extract_engine_signal()
       (neutral stockfish_json — no engine process required for chat).
    2. Build a deterministic context block: evaluation band, game phase,
       player profile, past mistakes.
    3. Assemble a coaching reply that always cites the engine evaluation.
    4. Return ChatReply(reply, engine_signal, mode="CHAT_V1").

Constraints
-----------
- No reinforcement learning.
- No dynamic skill adaptation.
- reply always references the engine evaluation band and phase.
- engine_signal is always produced by extract_engine_signal(), never
  sourced from or overridden by any user-provided text.
- SafeExplainer produces the base evaluation sentence deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass

from llm.rag.engine_signal.extract_engine_signal import extract_engine_signal
from llm.seca.explainer.safe_explainer import SafeExplainer

_safe_explainer = SafeExplainer()

# ---------------------------------------------------------------------------
# Label tables (deterministic)
# ---------------------------------------------------------------------------

_BAND_LABEL: dict[str, str] = {
    "equal": "equal",
    "small_advantage": "a small advantage",
    "clear_advantage": "a clear advantage",
    "decisive_advantage": "a decisive advantage",
}

_PHASE_HINT: dict[str, str] = {
    "opening": "In the opening, prioritise development and centre control.",
    "middlegame": "In the middlegame, look for tactical motifs and improve piece activity.",
    "endgame": "In the endgame, activate the king and convert any material advantage.",
}

_DELTA_HINT: dict[str, str] = {
    "increase": "The position is improving for the side to move.",
    "decrease": "The position has deteriorated — caution is warranted.",
    "stable": "The evaluation is stable.",
}

# ---------------------------------------------------------------------------
# Question-type detection and level-differentiated coaching advice
# ---------------------------------------------------------------------------

_QUESTION_KEYWORDS: dict[str, list[str]] = {
    "endgame": [
        "endgame", "end game", "convert", "king activity", "rook end",
        "pawn end", "winning endgame",
    ],
    "opening": [
        "opening", "develop", "castle", "center", "centre", "piece out", "start",
    ],
    "strategic": [
        "plan", "strategy", "strategic", "structure", "long-term", "weak square",
        "outpost", "pawn chain", "imbalance",
    ],
    "tactical": [
        "tactic", "attack", "fork", "pin", "hanging", "capture",
        "threat", "combination", "sacrifice", "material", "win material",
    ],
}

_COACHING_ADVICE: dict[str, dict[str, str]] = {
    "tactical": {
        "beginner": (
            "Check if any pieces on the board are unprotected — "
            "these are often the first targets in tactics."
        ),
        "intermediate": (
            "Look for forcing moves: checks, captures, and threats. "
            "Undefended pieces are potential tactical targets."
        ),
        "advanced": (
            "Calculate all forcing lines. Assess candidate moves systematically: "
            "checks, captures, then threats."
        ),
    },
    "opening": {
        "beginner": (
            "Try to move each piece only once, control the centre with pawns, "
            "and get your king to safety."
        ),
        "intermediate": (
            "Develop purposefully: control the centre, avoid early queen moves, "
            "and coordinate your pieces before castling."
        ),
        "advanced": (
            "The pawn structure defines the resulting middlegame. "
            "Assess structural imbalances and plan accordingly."
        ),
    },
    "endgame": {
        "beginner": (
            "Activate your king — it becomes a powerful piece in the endgame. "
            "Push your passed pawns."
        ),
        "intermediate": (
            "Use your king actively, centralise your rook, and look for pawn breaks "
            "to create a passed pawn."
        ),
        "advanced": (
            "Precise technique is essential. Determine key factors: "
            "king activity, pawn structure, and piece coordination."
        ),
    },
    "strategic": {
        "beginner": (
            "Find your least-active piece and look for a better square for it."
        ),
        "intermediate": (
            "Identify pawn weaknesses on both sides. Place your pieces on strong squares "
            "where they cannot easily be chased away."
        ),
        "advanced": (
            "Assess all imbalances: pawn structure, piece activity, weak squares, "
            "and pawn majorities. Create a concrete plan."
        ),
    },
    "general": {
        "beginner": (
            "Focus on piece safety first, then look for ways to improve your position."
        ),
        "intermediate": (
            "Consider the engine evaluation and think about your next two or three moves as a plan."
        ),
        "advanced": (
            "Evaluate the position's key features: material, pawn structure, "
            "piece activity, and king safety."
        ),
    },
}


def _detect_question_type(query: str) -> str:
    q = query.lower()
    for qtype, keywords in _QUESTION_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return qtype
    return "general"


def _map_skill_level(player_profile: dict | None) -> str:
    if not player_profile:
        return "intermediate"
    skill = str(player_profile.get("skill_estimate", "")).lower()
    if "beginner" in skill or "novice" in skill:
        return "beginner"
    if "advanced" in skill or "expert" in skill or "master" in skill or "club" in skill:
        return "advanced"
    return "intermediate"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatTurn:
    """A single turn in the conversation (user or assistant)."""

    role: str  # "user" | "assistant"
    content: str


@dataclass(frozen=True)
class ChatReply:
    """Result of generate_chat_reply().

    Attributes
    ----------
    reply : str
        Coaching reply that always references the engine evaluation.
    engine_signal : dict
        Structured engine signal from extract_engine_signal(); never
        derived from LLM or user input.
    mode : str
        Always "CHAT_V1" for this pipeline.
    """

    reply: str
    engine_signal: dict
    mode: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_engine_context(engine_signal: dict) -> str:
    """Produce a one-line engine evaluation summary sentence.

    Always mentions the evaluation type (cp/mate), band, side, and
    current game phase so the reply contractually references engine eval.
    """
    eval_info = engine_signal.get("evaluation", {})
    band = eval_info.get("band", "equal")
    side = eval_info.get("side", "unknown")
    eval_type = eval_info.get("type", "cp")
    phase = engine_signal.get("phase", "middlegame")
    delta = engine_signal.get("eval_delta", "stable")

    if eval_type == "mate":
        eval_sentence = f"The engine sees a forced mate ({side} is winning)."
    else:
        band_label = _BAND_LABEL.get(band, band.replace("_", " "))
        eval_sentence = f"Engine evaluation: {side} has {band_label} [{phase}]."

    delta_hint = _DELTA_HINT.get(delta, "")
    return f"{eval_sentence} {delta_hint}".strip()


def _build_context_block(
    engine_signal: dict,
    player_profile: dict | None,
    past_mistakes: list[str] | None,
    move_count: int | None = None,
) -> str:
    """Assemble all available coaching context into a single paragraph.

    Always leads with the engine evaluation reference.  Player profile,
    past mistakes, and move count are appended when present.
    """
    parts = [_format_engine_context(engine_signal)]

    if move_count is not None:
        parts.append(f"This is move {move_count} of the game.")

    if player_profile:
        skill = player_profile.get("skill_estimate", "")
        mistakes = player_profile.get("common_mistakes", [])
        strengths = player_profile.get("strengths", [])
        if skill:
            parts.append(f"Player skill level: {skill}.")
        if mistakes:
            tags = [(m.get("tag", str(m)) if isinstance(m, dict) else str(m)) for m in mistakes[:3]]
            parts.append(f"Recurring mistake areas: {', '.join(tags)}.")
        if strengths:
            parts.append(f"Strengths: {', '.join(str(s) for s in strengths[:2])}.")

    if past_mistakes:
        parts.append(f"Recent training focus: {', '.join(past_mistakes[:3])}.")

    return " ".join(parts)


def _build_reply(
    user_query: str,
    context_block: str,
    engine_signal: dict,
    base_explanation: str,
    history: list[ChatTurn],
    skill_level: str = "intermediate",
) -> str:
    """Build the final coaching reply.

    Structure:
        [previous topic reference if applicable]
        [engine context block — always present]
        [move quality note if available]
        [base explanation from SafeExplainer]
        [response to user query]
    """
    parts: list[str] = []

    # Reference a prior user question when the conversation has history
    prior_user_turns = [t for t in history[:-1] if t.role == "user"]
    if prior_user_turns:
        prev = prior_user_turns[-1].content[:80].strip()
        parts.append(f'Following up on your earlier question about "{prev}":')

    # Engine context always leads the reply
    parts.append(context_block)

    # Move quality note (if the engine reported one)
    move_quality = engine_signal.get("last_move_quality", "")
    if move_quality and move_quality not in ("unknown", ""):
        parts.append(f"Last move quality: {move_quality}.")

    # Base evaluation from SafeExplainer
    if base_explanation:
        parts.append(base_explanation)

    # Address the user's specific query with level-differentiated coaching advice
    query = user_query.strip()
    if query:
        question_type = _detect_question_type(query)
        advice = _COACHING_ADVICE[question_type][skill_level]
        parts.append(f'On your question "{query}": {advice}')

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_chat_reply(
    fen: str,
    messages: list[ChatTurn],
    player_profile: dict | None = None,
    past_mistakes: list[str] | None = None,
    move_count: int | None = None,
) -> ChatReply:
    """Generate a deterministic coaching reply for the current chat turn.

    Parameters
    ----------
    fen:
        Current board position (FEN string).  Must be a valid FEN or
        "startpos".
    messages:
        Full conversation history including the latest user message at
        the end.  May be empty (produces a position-only analysis reply).
    player_profile:
        Optional SECA player model dict with keys skill_estimate,
        common_mistakes (list of {tag, count}), and strengths (list[str]).
    past_mistakes:
        Optional list of MistakeCategory strings from the analytics layer.
    move_count:
        Optional number of half-moves played so far; injected into the
        context block so the LLM knows the game phase ("This is move N of
        the game.").  None omits the field.

    Returns
    -------
    ChatReply
        reply (str)        — coaching reply always referencing engine eval.
        engine_signal (dict) — from extract_engine_signal(); never from LLM.
        mode (str)         — always "CHAT_V1".
    """
    # Engine signal always from extract_engine_signal, never user-supplied
    engine_signal = extract_engine_signal({}, fen=fen)

    # Deterministic base explanation from SafeExplainer
    base_explanation = _safe_explainer.explain(engine_signal)

    # Context block (always includes engine evaluation reference)
    context_block = _build_context_block(
        engine_signal, player_profile, past_mistakes, move_count
    )

    # Latest user message (may be empty for session-open call)
    user_turns = [t for t in messages if t.role == "user"]
    user_query = user_turns[-1].content if user_turns else ""

    skill_level = _map_skill_level(player_profile)

    reply = _build_reply(
        user_query=user_query,
        context_block=context_block,
        engine_signal=engine_signal,
        base_explanation=base_explanation,
        history=messages,
        skill_level=skill_level,
    )

    return ChatReply(reply=reply, engine_signal=engine_signal, mode="CHAT_V1")
