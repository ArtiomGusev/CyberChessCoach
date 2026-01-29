from pathlib import Path

_SYSTEM_PROMPT = Path(
    "rag/prompts/system_v2_mode_2.txt"
).read_text(encoding="utf-8")


def render_mode_2_prompt(
    *,
    engine_signal: dict,
    rag_context: list,
    fen: str,
    user_query: str = "",
) -> str:
    parts = []

    # 1. System prompt (verbatim, first)
    parts.append(_SYSTEM_PROMPT)

    # 2. Engine signal (verbatim)
    parts.append("\nENGINE SIGNAL:")
    parts.append(str(engine_signal))

    # 3. Retrieved context (verbatim summaries only)
    if rag_context:
        parts.append("\nEXPLANATORY CONTEXT:")
        for doc in rag_context:
            parts.append(f"- {doc['content']['description']}")

    # 4. FEN (no interpretation)
    parts.append("\nPOSITION (FEN):")
    parts.append(fen)

    # 5. Optional user question
    if user_query:
        parts.append("\nUSER QUESTION:")
        parts.append(user_query)

    return "\n".join(parts)
