"""
Per-move live coaching pipeline — deterministic, no RL.

Architecture
------------
Inputs:
    fen         Current board position (FEN string) after the move.
    uci         The move just played in UCI notation (e.g. "e2e4").
    player_id   Player identifier (reserved for future profile enrichment).

Processing:
    1. Extract engine signal from the FEN via extract_engine_signal()
       (neutral stockfish_json — no engine process required).
    2. Build a coaching hint that always cites the engine evaluation band,
       game phase, and move quality.
    3. Return LiveMoveReply(hint, engine_signal, move_quality, mode="LIVE_V1").

Constraints
-----------
- No reinforcement learning.
- No dynamic skill adaptation.
- hint always references the engine evaluation band and phase.
- engine_signal is always produced by extract_engine_signal(), never
  sourced from or overridden by any user-provided text.
- SafeExplainer produces the base evaluation sentence deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass

from llm.confidence_language_controller import compute_urgency
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
    "opening": "Keep developing your pieces and controlling the centre.",
    "middlegame": "Look for tactical motifs and improve piece activity.",
    "endgame": "Activate your king and convert any material advantage.",
}

_QUALITY_COMMENT: dict[str, str] = {
    "blunder": "That was a blunder — try to find a better continuation.",
    "mistake": "That move was a mistake — consider the alternatives.",
    "inaccuracy": "A slight inaccuracy — you had a stronger option.",
    "good": "Good move — that was a strong choice.",
    "excellent": "Excellent move — that is one of the best continuations.",
    "best": "Best move — the engine agrees that is optimal.",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LiveMoveReply:
    """Result of generate_live_reply().

    Attributes
    ----------
    hint : str
        Coaching hint for this move, always referencing engine evaluation.
    engine_signal : dict
        Structured engine signal from extract_engine_signal(); never
        derived from user input.
    move_quality : str
        last_move_quality from the engine signal, or "unknown".
    mode : str
        Always "LIVE_V1" for this pipeline.
    """

    hint: str
    engine_signal: dict
    move_quality: str
    mode: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_hint(
    uci: str,
    engine_signal: dict,
    base_explanation: str,
    explanation_style: str | None = None,
) -> str:
    """Build a deterministic per-move coaching hint.

    Always leads with the engine evaluation reference.  Appends move-quality
    feedback and a phase-specific tip when available.

    Parameters
    ----------
    explanation_style:
        Optional style from the player's skill profile.
        - None / "intermediate": all parts except base explanation
          (current default behaviour — backwards-compatible).
        - "simple":  eval sentence + quality comment only (beginners:
          concise feedback, no technical detail).
        - "advanced": all parts including the technical base explanation.
    """
    eval_info = engine_signal.get("evaluation", {})
    band = eval_info.get("band", "equal")
    side = eval_info.get("side", "unknown")
    eval_type = eval_info.get("type", "cp")
    phase = engine_signal.get("phase", "middlegame")
    move_quality = engine_signal.get("last_move_quality", "unknown")

    parts: list[str] = []

    # 0. Urgency prefix from confidence_language_controller — keeps tone appropriate.
    urgency = compute_urgency(engine_signal)
    if urgency == "critical":
        parts.append("Attention:")

    # 1. Engine evaluation sentence — always present
    if eval_type == "mate":
        parts.append(f"Engine: forced mate ({side} is winning).")
    else:
        band_label = _BAND_LABEL.get(band, band.replace("_", " "))
        parts.append(f"Engine: {side} has {band_label} [{phase}].")

    # 2. Move quality comment (only when the engine provided a known label)
    quality_comment = _QUALITY_COMMENT.get(move_quality, "")
    if quality_comment:
        parts.append(quality_comment)

    # 3. Base evaluation sentence from SafeExplainer — only for advanced players.
    # Omitted for simple/intermediate styles to keep feedback concise.
    if base_explanation and explanation_style == "advanced":
        parts.append(base_explanation)

    # 4. Phase-specific coaching tip — omitted for simple style (keep hint short).
    if explanation_style != "simple":
        phase_tip = _PHASE_HINT.get(phase, "")
        if phase_tip:
            parts.append(phase_tip)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_live_reply(
    fen: str,
    uci: str,
    player_id: str = "demo",
    explanation_style: str | None = None,
    stockfish_json: dict | None = None,
) -> LiveMoveReply:
    """Generate a deterministic coaching hint for a single move.

    Parameters
    ----------
    fen :
        Board position after the move was played (FEN string).
        Must be a valid FEN or "startpos".
    uci :
        The move just played in UCI notation (e.g. "e2e4", "e7e8q").
    player_id :
        Player identifier — stored for reference but not reflected in the
        engine signal (engine truth is always from extract_engine_signal).
    explanation_style :
        Player skill style from compute_adaptation()["teaching"]["style"].
        One of "simple", "intermediate", "advanced", or None (defaults to
        "intermediate" behaviour: eval + quality + phase tip).

    Returns
    -------
    LiveMoveReply
        hint (str)           — coaching hint always referencing engine eval.
        engine_signal (dict) — from extract_engine_signal(); never from user.
        move_quality (str)   — engine's last_move_quality or "unknown".
        mode (str)           — always "LIVE_V1".
    """
    # Engine signal always from extract_engine_signal, never user-supplied
    engine_signal = extract_engine_signal(stockfish_json or {}, fen=fen)

    # Deterministic base explanation from SafeExplainer
    base_explanation = _safe_explainer.explain(engine_signal)

    # Move quality from the engine signal (not from user input)
    move_quality = engine_signal.get("last_move_quality", "unknown")

    hint = _build_hint(uci, engine_signal, base_explanation, explanation_style=explanation_style)

    return LiveMoveReply(
        hint=hint,
        engine_signal=engine_signal,
        move_quality=move_quality,
        mode="LIVE_V1",
    )
