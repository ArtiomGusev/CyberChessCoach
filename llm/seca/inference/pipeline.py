# seca/inference/pipeline.py

from llm.seca.engines.stockfish import analyze
from llm.seca.rag.retrieve import retrieve_docs
from llm.seca.llm.explain import generate_explanation
from llm.seca.players.skill_update import update_skill
from llm.seca.telemetry.log import log_event


async def explain_position(req: dict):
    fen = req["fen"]
    player_id = req["player_id"]

    engine_signal = analyze(fen)
    docs = retrieve_docs(engine_signal)

    explanation = generate_explanation(engine_signal, docs)

    update_skill(player_id, engine_signal)
    log_event(player_id, engine_signal, explanation)

    return {"explanation": explanation}
