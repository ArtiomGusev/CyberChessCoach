import os

import httpx

from llm.rag.engine_signal.extract_engine_signal import extract_engine_signal
from llm.rag.retriever.retriever import retrieve
from llm.rag.documents import ALL_RAG_DOCUMENTS
from llm.rag.prompts.mode_2.render import render_mode_2_prompt
from llm.rag.prompts.system_v2_mode_2 import SYSTEM_PROMPT
from llm.rag.validators.mode_2_negative import validate_mode_2_negative
from llm.confidence_language_controller import build_language_controller_block


_ollama_base = os.getenv("COACH_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_URL = f"{_ollama_base}/api/generate"
MODEL_NAME = os.getenv("COACH_OLLAMA_MODEL", "qwen2.5:7b-instruct-q2_K")

MAX_RETRIES = 2


# ---------------------------------------------------------
# LLM CALL
# ---------------------------------------------------------

def call_llm(prompt: str) -> str:
    response = httpx.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )

    response.raise_for_status()
    return response.json()["response"].strip()


# ---------------------------------------------------------
# SINGLE EXPLANATION ATTEMPT
# ---------------------------------------------------------

def generate_once(fen: str, stockfish_json: dict, user_query: str) -> tuple[str, dict]:
    esv = extract_engine_signal(stockfish_json, fen=fen)

    rag_docs = retrieve(esv, ALL_RAG_DOCUMENTS)

    style_block = build_language_controller_block(esv)
    prompt = render_mode_2_prompt(
        system_prompt=SYSTEM_PROMPT + "\n\n" + style_block,
        engine_signal=esv,
        rag_docs=rag_docs,
        fen=fen,
        user_query=user_query or "",
    )

    explanation = call_llm(prompt)

    return explanation, esv


# ---------------------------------------------------------
# VALIDATED EXPLANATION WITH RETRY
# ---------------------------------------------------------

def generate_validated_explanation(
    fen: str,
    stockfish_json: dict,
    user_query: str | None = "",
):
    last_error = None

    for _ in range(MAX_RETRIES + 1):
        explanation, esv = generate_once(fen, stockfish_json, user_query or "")

        try:
            validate_mode_2_negative(explanation)
            return explanation, esv  # ✅ success
        except AssertionError as e:
            last_error = str(e)

            # Retry hint appended to query
            user_query = (user_query or "") + (
                "\n\nIMPORTANT: Follow MODE-2 rules strictly. "
                "Do NOT speculate, invent moves, or mention engine intentions."
            )

    # If all retries failed → return safe fallback
    return (
        "I cannot provide a fully reliable explanation for this position "
        "without violating analysis constraints. Please try another position.",
        esv,
    )
