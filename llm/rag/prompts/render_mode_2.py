def render_mode_2_prompt(
    *,
    engine_signal: dict,
    rag_context: list,
    fen: str,
    user_query: str = "",
) -> str:
    """
    Render the Mode-2 prompt.

    All inputs are injected verbatim.
    No logic, no inference, no mutation.
    """

    parts = []

    parts.append("SYSTEM PROMPT:")
    parts.append(engine_signal["system_prompt"] if "system_prompt" in engine_signal else "")

    parts.append("\nENGINE SIGNAL:")
    parts.append(str(engine_signal))

    parts.append("\nRAG CONTEXT:")
    for doc in rag_context:
        parts.append(f"- {doc['content']['description']}")

    parts.append("\nFEN:")
    parts.append(fen)

    if user_query:
        parts.append("\nUSER QUESTION:")
        parts.append(user_query)

    return "\n".join(parts)
