Local dev: using Fake LLM

You can run the embedded API locally without a real LLM by using the FakeLLM.
Set the `LLM_MODEL` env var to `fake` or `fake:<mode>` before running scripts.

Examples:
- PowerShell (temporary for session):
  $Env:LLM_MODEL = 'fake:mate_softening'
  python test_explain.py

- Command Prompt (temporary):
  set LLM_MODEL=fake:mate_softening && python test_explain.py

Supported fake modes (examples):
- `compliant` — returns a compliant explanation
- `forbidden_phrase` — returns text containing forbidden phrases
- `missing_data_violation` — returns text missing required missing-data acknowledgements
- `mate_softening` — returns text that softens mate claims

This is useful for iterating tests and debugging `run_mode_2` without depending on external LLM services.

Optional CI-only real-LLM test

- The repository includes an optional test that runs a representative case against a real LLM. It is **skipped by default**.
- To enable it in CI or locally, set:
  - `RUN_REPR_CI=1` and ensure `LLM_MODEL` is set to your real model name.

Examples:
- PowerShell (temporary):
  $Env:RUN_REPR_CI = '1'; $Env:LLM_MODEL = 'qwen2.5:7b-instruct-q2_K'; python -m pytest -q rag/tests/test_ci_optional_run.py
- Command Prompt (temporary):
  set RUN_REPR_CI=1 && set LLM_MODEL=qwen2.5:7b-instruct-q2_K && python -m pytest -q rag/tests/test_ci_optional_run.py

Use this to verify end-to-end behavior when a real model is available.

Docker runtime for low-latency Stockfish

- A pooled Stockfish runtime is available via `docker-compose.yml` and `Dockerfile.api`.
- It pre-spawns engine workers, keeps them alive, and uses Redis FEN caching.

Start:
- `docker compose up --build`

Main env knobs:
- `ENGINE_POOL_SIZE` (default `8`)
- `ENGINE_THREADS` (default `1`)
- `ENGINE_HASH_MB` (default `128`)
- `ENGINE_DEFAULT_MOVETIME_MS` (default `40`)
- `ENGINE_TRAINING_MOVETIME_MS` (default `40`)
- `ENGINE_ANALYSIS_MOVETIME_MS` (default `80`)
- `ENGINE_BLITZ_MOVETIME_MS` (default `25`)
- `ENGINE_QUEUE_TIMEOUT_MS` (default `50`; queue wait guard before fallback)
- `MOVE_CACHE_TTL_SECONDS` (default `3600`)
- `ENGINE_PREWARM_MODES` (default `blitz`; comma-separated)
- `ENGINE_PREWARM_FENS` (default includes `startpos`, `1.e4 e5`, `1.d4 d5`; override with `||`-separated FENs)
