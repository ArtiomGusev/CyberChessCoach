import re

FORBIDDEN_PATTERNS = [
    r"\bcheckmate\b",
    r"\bmate in\b",
    r"\bforced mate\b",

    r"\b(should|must|needs to|best move)\b",
    r"\bplay\b\s+[a-h][1-8]",

    r"\b[BNRQK]?[a-h][1-8](x[a-h][1-8])?(=[BNRQ])?\+?\b",
    r"\b0-0\b|\b0-0-0\b",
    r"\b1-0\b|\b0-1\b|\b½-½\b",

    r"\bafter\b\s+[a-h][1-8]",
    r"\bfollowed by\b",

    r"\b(blundered|carelessly|intended|overlooked|failed to see)\b",

    r"\bactually winning\b",
    r"\bdespite the evaluation\b",
]


def validate_mode_2_negative(text: str) -> None:
    lowered = text.lower()

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered):
            raise AssertionError(
                f"Mode-2 violation detected: pattern `{pattern}`"
            )
