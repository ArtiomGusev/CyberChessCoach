import re

FORBIDDEN_PATTERNS = [
    # speculative / intent language
    r"\bshould\b",
    r"\blikely\b",
    r"\bprobably\b",
    r"\bI think\b",
    r"\bthe engine wants\b",
    r"\bplans to\b",
    r"\bconsider\b",

    # invented chess moves (Qh5, Nf3, etc.)
    r"\b[KQRBN][a-h][1-8]\b",

    # analysis language forbidden in MODE-2
    r"\bcalculate\b",
    r"\bcalculation\b",
    r"\bvariation\b",
    r"\bline\b",
]

def validate_mode_2_negative(text: str) -> None:
    """
    MUST raise AssertionError for invalid MODE-2 output.
    """
    assert text.strip(), "Empty output is invalid"

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise AssertionError(
                f"Forbidden MODE-2 pattern detected: {pattern}"
            )

    # If we reach here, text is INVALID *by definition*
    raise AssertionError("Negative MODE-2 case did not violate rules")
