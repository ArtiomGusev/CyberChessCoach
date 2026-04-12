print(">>> USING extract_engine_signal FROM:", __file__)


def side_from_fen(fen: str | None) -> str | None:
    if not fen:
        return None
    try:
        return "white" if fen.split()[1] == "w" else "black"
    except Exception:
        return None


def extract_engine_signal(
    stockfish_json: dict | None,
    *,
    fen: str | None = None,
) -> dict:
    stockfish_json = stockfish_json or {}

    evaluation = stockfish_json.get("evaluation", {})
    eval_type = evaluation.get("type", "cp")
    _raw_value = evaluation.get("value", 0)
    try:
        value = int(_raw_value)
    except (TypeError, ValueError):
        value = 0

    def side_from_fen(fen: str | None) -> str | None:
        if not fen:
            return None
        try:
            return "white" if fen.split()[1] == "w" else "black"
        except Exception:
            return None

    # -------------------------
    # MATE (TERMINAL STATE)
    # -------------------------
    if eval_type == "mate":
        side = side_from_fen(fen)
        if side not in ("white", "black"):
            side = "unknown"

        delta = stockfish_json.get("eval_delta", 0)
        if delta >= 50:
            eval_delta = "increase"
        elif delta <= -50:
            eval_delta = "decrease"
        else:
            eval_delta = "stable"

        return {
            "evaluation": {
                "type": "mate",
                "band": "decisive_advantage",
                "side": side,
            },
            "eval_delta": eval_delta,
            "last_move_quality": stockfish_json.get("errors", {}).get(
                "last_move_quality", "unknown"
            ),
            "tactical_flags": stockfish_json.get("tactical_flags", []),
            "position_flags": stockfish_json.get("position_flags", []),
            "phase": stockfish_json.get("phase", "middlegame"),
        }

    # -------------------------
    # CP (NON-TERMINAL STATE)
    # -------------------------
    cp = abs(value)
    if cp <= 20:
        band = "equal"
    elif cp <= 60:
        band = "small_advantage"
    elif cp <= 120:
        band = "clear_advantage"
    else:
        band = "decisive_advantage"

    # Schema contract: value is centipawns from White's perspective.
    # Positive  → White is ahead  → white has the advantage.
    # Negative  → Black is ahead  → black has the advantage.
    # Zero      → equal; attribute to black by convention (band="equal" is primary).
    side = "white" if value > 0 else "black"

    delta = stockfish_json.get("eval_delta", 0)
    if delta >= 50:
        eval_delta = "increase"
    elif delta <= -50:
        eval_delta = "decrease"
    else:
        eval_delta = "stable"

    return {
        "evaluation": {
            "type": "cp",
            "band": band,
            "side": side,
        },
        "eval_delta": eval_delta,
        "last_move_quality": stockfish_json.get("errors", {}).get("last_move_quality", "unknown"),
        "tactical_flags": stockfish_json.get("tactical_flags", []),
        "position_flags": stockfish_json.get("position_flags", []),
        "phase": stockfish_json.get("phase", "middlegame"),
    }
