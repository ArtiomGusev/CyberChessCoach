import os

from rag.engine_signal.extract_engine_signal import extract_engine_signal
from rag.retriever import retrieve
from rag.documents import ALL_RAG_DOCUMENTS
from rag.prompts.render_mode_2 import render_mode_2_prompt
from rag.llm.ollama import OllamaLLM
from rag.llm.run_mode_2 import run_mode_2



# ---- Load deployment config (edge only) ----

DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "DEV")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
VALIDATION = os.getenv("MODE_2_VALIDATION") == "ENFORCED"

if not LLM_MODEL:
    raise RuntimeError("LLM_MODEL must be set")


# ---- Initialize real LLM once ----

_REAL_LLM = OllamaLLM(
    model=LLM_MODEL,
    temperature=LLM_TEMPERATURE,
)


# ---- Embedded public API ----

def explain_position(payload: dict) -> str:
    """
    Embedded Mode-2 explanation entry point.

    REQUIRED payload keys:
      - fen
      - engine_json
      - case_type

    OPTIONAL:
      - user_query
    """

    esv = extract_engine_signal(payload["engine_json"])

    rag_docs = retrieve(esv, ALL_RAG_DOCUMENTS)

    prompt = render_mode_2_prompt(
        engine_signal=esv,
        rag_context=rag_docs,
        fen=payload["fen"],
        user_query=payload.get("user_query", ""),
    )

    return run_mode_2(
    llm=_REAL_LLM,
    prompt=prompt,
    case_type=payload["case_type"],
)

