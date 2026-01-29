def score_explanation(
    *,
    text: str,
    engine_signal: dict,
) -> int:
    score = 0

    # 1. Engine alignment
    eval_info = engine_signal.get("evaluation", {})
    if eval_info:
        band = eval_info.get("band", "")
        if band and band.replace("_", " ") in text.lower():
            score += 2
        elif band:
            score += 1

    # 2. Causality
    causal_markers = [
        "because",
        "due to",
        "explains",
        "reflects",
        "results from",
    ]
    if any(m in text.lower() for m in causal_markers):
        score += 2
    else:
        score += 1  # neutral explanations still acceptable

    # 3. Completeness
    flags = []
    if engine_signal.get("last_move_quality"):
        flags.append("mistake")
    flags += engine_signal.get("tactical_flags", [])
    flags += engine_signal.get("position_flags", [])

    covered = sum(
        1 for f in flags if f.replace("_", " ") in text.lower()
    )

    if flags:
        ratio = covered / len(flags)
        if ratio > 0.8:
            score += 2
        elif ratio > 0.3:
            score += 1

    # 4. Mode-2 discipline (soft check)
    forbidden_soft = ["should", "best move", "consider"]
    if not any(w in text.lower() for w in forbidden_soft):
        score += 2
    else:
        score += 1

    # 5. Clarity
    if len(text.splitlines()) >= 2:
        score += 2
    else:
        score += 1

    return score
