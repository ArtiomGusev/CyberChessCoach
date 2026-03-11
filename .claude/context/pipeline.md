# Pipeline Context

## Mode-2 Explanation Pipeline

The architecture guard for explanations is:

1. Stockfish or engine analysis provides trusted chess state.
2. Engine Signal Vector (ESV) or normalized engine output is derived deterministically.
3. RAG retrieval selects explanatory material.
4. Prompt rendering assembles engine signal, context, FEN, and optional query.
5. The LLM generates explanation text as an untrusted realizer.
6. Validators enforce no move suggestions, no invented facts, and correct missing-data or mate handling.
7. The final response is returned only after validation.

No step should be skipped or reordered.

## Engine Evaluation Request Flow

For `llm/host_app.py`:

1. Request arrives at `/engine/eval`.
2. Request limits are normalized by `EngineEvaluator.resolve_limits`.
3. Position input is normalized from FEN and moves.
4. `EliteEngineService` evaluates through the engine pool and opening book integration.
5. Cache and miss metrics are updated.
6. Response returns engine result plus `_metrics`.

## Post-Game / SECA Flow

For `llm/seca/events/router.py`:

1. Auth identifies the current player.
2. Game result and weaknesses are stored.
3. Skill updates and rating/confidence updates are persisted.
4. Post-game coaching chooses an action and payload.
5. Safe mode gates experimental learning paths.
6. Response returns rating, confidence, learning status, and coach output.
