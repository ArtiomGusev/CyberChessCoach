def build_plan(engine_signal: dict, skill_level: int) -> dict:
    if engine_signal["evaluation"]["type"] == "mate":
        focus = "urgency"
    elif skill_level < 1200:
        focus = "simple_blunder"
    else:
        focus = "strategic_balance"

    return {
        "focus": focus,
        "max_depth": 2 if skill_level < 1200 else 4,
    }
