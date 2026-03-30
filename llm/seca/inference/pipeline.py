# seca/inference/pipeline.py
#
# Stub — the underlying modules (rag, llm.explain, players.skill_update,
# telemetry) are not yet implemented.  Imports are deferred inside the
# function body so that `import llm.server` does not fail at startup.


async def explain_position(req: dict):
    from llm.seca.engines.stockfish import StockfishEnginePool  # noqa: F401
    from llm.seca.rag.retrieve import retrieve_docs  # type: ignore[import]
    from llm.seca.llm.explain import generate_explanation  # type: ignore[import]
    from llm.seca.players.skill_update import update_skill  # type: ignore[import]
    from llm.seca.telemetry.log import log_event  # type: ignore[import]

    raise NotImplementedError(
        "inference/pipeline.py is a stub — the backing modules are not yet implemented"
    )
