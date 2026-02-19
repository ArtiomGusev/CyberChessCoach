from llm.rag.engine_signal.extract_engine_signal import extract_engine_signal
from llm.rag.retriever.retriever import retrieve
from llm.rag.prompts.mode_2.render import render_mode_2_prompt
from llm.rag.documents import ALL_RAG_DOCUMENTS


def analyze_position(payload: dict) -> dict:
    esv = extract_engine_signal(payload["stockfish_json"], fen=payload["fen"])
    rag_docs = retrieve(esv, ALL_RAG_DOCUMENTS)

    prompt = render_mode_2_prompt(
        system_prompt="SYSTEM",
        engine_signal=esv,
        rag_docs=rag_docs,
        fen=payload["fen"],
        user_query=payload.get("user_query", ""),
    )

    return {
        "prompt": prompt,
        "engine_signal": esv,
    }
