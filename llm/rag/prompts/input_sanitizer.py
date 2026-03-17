"""
Prompt injection sanitizer for user-supplied input.

Strategy:
  1. Strip null bytes and non-printable control characters (keep \\n, \\r, \\t).
  2. Detect known injection patterns and raise ValueError so the caller can
     reject the request early (HTTP 422 at schema validation) or route to a
     safe fallback at pipeline entry — rather than relying on the LLM to
     ignore the injected instruction.
  3. Truncate to the max allowed length as a last-resort safeguard.

This is a *pre-LLM* defence. Post-LLM output validation is handled separately
in llm/rag/validators/ and llm/rag/llm/run_mode_2.py.

Idempotency guarantee
---------------------
sanitize_user_query is safe to call at multiple defence points:
  - Clean inputs  : pass through unchanged on every call (idempotent).
  - Injected inputs: raise ValueError on the *first* call; the request is
    rejected before it can reach a second call site.
Two call sites are intentional:
  1. server.py schema validation  → early API rejection (HTTP 422).
  2. explain_pipeline.py entry    → pipeline-level guard for direct calls.
Both are independent; the idempotency guarantee keeps double-call harmless.
"""

import logging
import re

logger = logging.getLogger(__name__)

MAX_USER_QUERY_LENGTH = 2000

# Patterns that indicate an attempt to override instructions.
# Matched case-insensitively anywhere in the text.
#
# Design notes:
#   - "verbatim" is intentionally *narrowed* to command-style contexts
#     (repeat/output/print/dump ... verbatim) to avoid false-positives on
#     legitimate chess questions that happen to use the word "verbatim".
#   - ChatML control tokens (<|im_start|>, <|im_end|>, <|system|>) are
#     included because Qwen2.5 uses ChatML format; injecting these tokens
#     in a user turn can escape the turn boundary.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous\s+)?instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous\s+)?instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\s+)?(normal\s+)?assistant", re.IGNORECASE),
    re.compile(r"reveal\s+(the\s+)?(hidden\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"repeat\s+(the\s+)?internal\s+instructions?", re.IGNORECASE),
    re.compile(r"print\s+(the\s+)?raw\s+engine\s+analysis", re.IGNORECASE),
    re.compile(r"output\s+(the\s+)?retrieved\s+context", re.IGNORECASE),
    # Narrowed verbatim: only flag command-style uses (not chess questions
    # that incidentally contain the word).
    re.compile(r"(repeat|output|print|dump)\b.{0,60}\bverbatim\b", re.IGNORECASE),
    # ChatML / Qwen2.5 format-injection tokens
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
]

# Control characters except TAB (0x09), LF (0x0A), CR (0x0D)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_user_query(text: str) -> str:
    """Return a sanitized copy of *text* safe to embed in an LLM prompt.

    Steps:
    - Strip dangerous control characters.
    - Raise ValueError if injection patterns are detected so the caller can
      reject the request or return a safe fallback without touching the LLM.
    - Truncate to MAX_USER_QUERY_LENGTH.

    Raises:
        ValueError: if prompt-injection patterns are detected in *text*.
    """
    if not text:
        return text

    # 1. Strip control characters
    cleaned = _CONTROL_CHAR_RE.sub("", text)

    # 2. Detect injection patterns — reject rather than label
    detected = [p.pattern for p in _INJECTION_PATTERNS if p.search(cleaned)]
    if detected:
        logger.warning(
            "Prompt injection detected in user_query — request rejected: %s",
            detected,
        )
        raise ValueError(
            f"Prompt injection detected ({len(detected)} pattern(s) matched). " "Request rejected."
        )

    # 3. Truncate
    if len(cleaned) > MAX_USER_QUERY_LENGTH:
        cleaned = cleaned[:MAX_USER_QUERY_LENGTH]

    return cleaned
