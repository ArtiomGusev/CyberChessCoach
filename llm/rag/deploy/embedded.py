import os

from rag.engine_signal.extract_engine_signal import extract_engine_signal
from rag.retriever import retrieve
from rag.documents import ALL_RAG_DOCUMENTS
from rag.prompts.render_mode_2 import render_mode_2_prompt
from rag.llm.ollama import OllamaLLM
from rag.llm.run_mode_2 import run_mode_2
from rag.meta.case_classifier import infer_case_type


# ---- Load deployment config (edge only) ----

DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "DEV")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
VALIDATION = os.getenv("MODE_2_VALIDATION") == "ENFORCED"


if not LLM_MODEL:
    raise RuntimeError("LLM_MODEL must be set")


# ---- Initialize real LLM once ----

if LLM_MODEL and LLM_MODEL.startswith("fake"):
    # Support selecting a FakeLLM with an optional mode via LLM_MODEL, e.g.:
    #   LLM_MODEL=fake             -> FakeLLM(mode="compliant")
    #   LLM_MODEL=fake:mate_softening -> FakeLLM(mode="mate_softening")
    from rag.llm.fake import FakeLLM

    parts = LLM_MODEL.split(":", 1)
    mode = parts[1] if len(parts) > 1 else "compliant"
    _REAL_LLM = FakeLLM(mode=mode)
else:
    _REAL_LLM = OllamaLLM(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
    )


# ---- Embedded public API ----

def explain_position(payload: dict) -> dict:
    if "engine_json" not in payload:
      raise ValueError("payload must include engine_json")

    """
    Input:
      {
        "fen": str,
        "engine_json": dict,
        "metadata": { ... }   # optional
      }

    Output:
      {
        "explanation": str,
        "confidence": "high" | "low",
        "tags": [ ... ]
      }
    """


    esv = extract_engine_signal(payload["engine_json"])

    rag_docs = retrieve(esv, ALL_RAG_DOCUMENTS)

    prompt = render_mode_2_prompt(
        engine_signal=esv,
        rag_context=rag_docs,
        fen=payload["fen"],
        user_query=payload.get("user_query", ""),
    )

    case_type = payload.get("case_type")
    if case_type is None:
        case_type = infer_case_type(esv)

    explanation_text = run_mode_2(
        llm=_REAL_LLM,
        prompt=prompt,
        case_type=case_type,
    )

    # Score and determine confidence
    from rag.quality.explanation_score import score_explanation
    from rag.llm.config import MIN_QUALITY_SCORE

    score = score_explanation(text=explanation_text, engine_signal=esv)
    confidence = "high" if score >= MIN_QUALITY_SCORE else "low"

    return {
        "explanation": explanation_text,
        "confidence": confidence,
        "tags": [],
    }

