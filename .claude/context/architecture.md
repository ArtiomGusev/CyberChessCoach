# Architecture Context

## System Map

- `android/`: Android client, JNI engine bridge, chat and coach UI.
- `llm/host_app.py`: engine-facing FastAPI service for evaluation, cache, and debug endpoints.
- `llm/server.py`: broader application API surface for moves, analysis, explanations, and training flow.
- `llm/rag/`: Mode-2 retrieval, prompt rendering, validators, and explanation quality logic.
- `llm/seca/`: SECA domain packages for auth, events, coaching, curriculum, player state, analytics, and storage.

## Architecture Laws

- Engine output is the chess source of truth.
- The LLM is untrusted. It explains, but does not decide or override engine truth.
- Mode-2 must preserve the deterministic pipeline defined in `ARCHITECTURE.md`.
- Validators, contracts, and prompt ordering must not be weakened to make tests pass.
- Autonomous RL behavior is prohibited, even though experimental planning and learning modules exist in the repo.

## Stable Boundaries

- Engine and evaluation logic belongs in `llm/engine_*`, `llm/elite_engine_service.py`, and `llm/seca/engines/`.
- RAG and explanation logic belongs in `llm/rag/`.
- SECA business logic belongs in `llm/seca/`.
- Android UI and JNI integration belong in `android/`.
- Cross-layer fixes should stay minimal and explicit.
