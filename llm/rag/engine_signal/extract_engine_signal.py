def extract_engine_signal(stockfish_json: dict) -> dict:
    evaluation = stockfish_json.get("evaluation", {})
    eval_type = evaluation.get("type", "cp")
    value = evaluation.get("value", 0)

    # Evaluation band
    if eval_type == "mate":
        band = "decisive_advantage"
    else:
        cp = abs(value)
        if cp <= 20:
            band = "equal"
        elif cp <= 60:
            band = "small_advantage"
        elif cp <= 120:
            band = "clear_advantage"
        else:
            band = "decisive_advantage"

    side = "white" if value < 0 else "black"

    # Eval delta
    delta = stockfish_json.get("eval_delta", 0)
    if delta >= 50:
        eval_delta = "increase"
    elif delta <= -50:
        eval_delta = "decrease"
    else:
        eval_delta = "stable"

    return {
        "evaluation": {
            "type": eval_type,
            "band": band,
            "side": side,
        },
        "eval_delta": eval_delta,
        "last_move_quality": stockfish_json.get("errors", {}).get(
            "last_move_quality", "unknown"
        ),
        "tactical_flags": stockfish_json.get("tactical_flags", []),
        "position_flags": stockfish_json.get("position_flags", []),
        "phase": "middlegame",  # temporary default for testing
    }
