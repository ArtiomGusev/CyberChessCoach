# Engine Context

## Core Components

- `llm/engine_pool.py`: manages a pool of async UCI workers.
- `llm/engine_eval.py`: normalizes limits, normalizes positions, evaluates positions, and maintains result caches.
- `llm/elite_engine_service.py`: wraps evaluation flow and opening book behavior.
- `llm/position_input.py`: canonicalizes FEN and move sequences before evaluation.
- `llm/seca/engines/stockfish/`: SECA-side stockfish adapter and pool abstractions.

## Engine Pool Rules

- Each worker runs one engine instance.
- Workers are configured at startup and returned to the pool after use.
- Missing Stockfish binaries should fail loudly, not silently downgrade behavior.
- Pool capacity, threads, hash, and startup pacing are environment-driven.

## Evaluation Rules

- Limit resolution clamps nodes and movetime to configured maxima.
- Cached engine results are keyed by normalized FEN plus nodes or movetime.
- Fast fallback behavior is allowed only as an explicit degraded path.
- Best move and score normalization must remain consistent across backend and JNI consumers.

## Guardrails

- Never let the LLM or Android client redefine engine semantics.
- Never change cache-key semantics without regression tests.
- Prefer minimal fixes in normalization, limit resolution, or pool lifecycle over broad rewrites.
