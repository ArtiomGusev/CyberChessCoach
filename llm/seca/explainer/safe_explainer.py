# llm/seca/explainer/safe_explainer.py

from typing import Dict


class SafeExplainer:
    """
    Deterministic explanation engine.
    Reads the ESV schema produced by extract_engine_signal().
    No LLM.
    """

    _BAND_MESSAGES: dict[str, str] = {
        "equal": "Position is roughly equal.",
        "small_advantage": "{side} has a slight advantage.",
        "clear_advantage": "{side} has a clear advantage.",
        "decisive_advantage": "{side} has a decisive advantage.",
    }

    _QUALITY_MESSAGES: dict[str, str] = {
        "best": "That was the best move.",
        "excellent": "Excellent move — a top continuation.",
        "good": "Good move — a solid choice.",
        "inaccuracy": "Slight inaccuracy — a stronger option existed.",
        "mistake": "That was a mistake.",
        "blunder": "That was a blunder.",
    }

    def explain(self, engine_signal: Dict) -> str:
        parts: list[str] = []

        eval_info = engine_signal.get("evaluation", {})
        eval_type = eval_info.get("type", "cp")
        band = eval_info.get("band", "equal")
        side = eval_info.get("side", "unknown")
        last_quality = engine_signal.get("last_move_quality", "unknown")

        # 1) Evaluation
        if eval_type == "mate":
            parts.append(f"Forced mate — {side} is winning.")
        else:
            template = self._BAND_MESSAGES.get(band, "Position is roughly equal.")
            parts.append(template.format(side=side.capitalize()))

        # 2) Move quality
        quality_msg = self._QUALITY_MESSAGES.get(last_quality, "")
        if quality_msg:
            parts.append(quality_msg)

        return " ".join(parts)
