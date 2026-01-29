FORBIDDEN_PHRASES = [
    "stockfish",
    "best move",
    "engine",
    "depth",
    "calculate",
    "variation",
]

REQUIRED_ON_MISSING = [
    "missing",
    "not enough information",
]

REQUIRED_ON_MATE = [
    "cannot be avoided",
    "inevitable",
]


def validate_output(text: str, *, case_type: str):
    lower = text.lower()

    for phrase in FORBIDDEN_PHRASES:
        if phrase in lower:
            raise AssertionError(f"Forbidden phrase detected: {phrase}")

    if case_type == "missing_data":
        if not any(p in lower for p in REQUIRED_ON_MISSING):
            raise AssertionError(
                "Missing-data response does not acknowledge missing information"
            )

    if case_type == "forced_mate":
        if not any(p in lower for p in REQUIRED_ON_MATE):
            raise AssertionError(
                "Forced-mate response does not emphasize inevitability"
            )
