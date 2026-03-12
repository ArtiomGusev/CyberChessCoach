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
- **Three distinct cache-key schemes are in use - they are not interchangeable:**
  - `EngineEvaluator` result cache (async, `llm/engine_eval.py`): in-memory LRU keys
    results as `{fen}:nodes:{n}` or `{fen}:movetime:{ms}`. Partitioned by FEN and
    resolved limit only. This cache has no TTL; entries are evicted only by the
    configured in-memory size bound.
  - `EliteEngineService` position cache (async, `llm/cache_keys.py` +
    `llm/position_cache.py`): Redis keys eval results as
    `cc:eval:<sha1(normalized_fen)[:12]>:<limit_suffix>`. TTL:
    `ENGINE_REDIS_CACHE_TTL_SECONDS` (default 86400 s).
  - `FenMoveCache` (sync, `llm/seca/engines/stockfish/pool.py`): keys Redis/LRU as
    `fen_move:v2:<sha256(fen|mode|target_elo|line_key)>`. Partitioned by FEN,
    mode, target ELO, and line context. `movetime_ms` is intentionally excluded from
    the digest (coarse-grained, not used for disambiguation). TTL: 3600 s.
  - These caches serve different layers and never share results directly.
  - Regression tests in `llm/tests/test_engine_eval_limits.py` protect the
    `EngineEvaluator` limit resolution and in-memory key behavior.
  - Regression tests in `llm/tests/test_fen_move_cache_key.py` protect the
    `FenMoveCache` key format.
- Fast fallback behavior is allowed only as an explicit degraded path.
  - Fallback results are stored in the LRU result cache. On a subsequent call for the
    same key, the cached fallback is returned with `engine_result_cache_hit=True` and
    `engine_fallback=False`. The degraded origin is invisible to callers on cache hits.
    See `llm/tests/test_engine_eval_fallback_cache.py`.
- Best move and score normalization must remain consistent across backend and JNI consumers.

## StockfishAdapter - Isolated / Dead Code

`llm/seca/engines/stockfish/adapter.py` contains `StockfishAdapter`, a simple
depth-limited wrapper around a single `chess.engine.SimpleEngine` instance. It is
**not** wired into any live request path. It must not be imported from `server.py`,
`host_app.py`, `elite_engine_service.py`, `engine_eval.py`, or `pool.py`.

Reasons it is excluded from live paths:
- Uses `chess.engine.Limit(depth=...)` - not governed by limit resolution.
- Runs its own `SimpleEngine` outside the pool lifecycle (no back-pressure, no release).
- Score output format (`{"type":"cp","value":N}`) differs from the normalized format
  (`{"score":N, "best_move":...}`) expected by all consumers.

The isolation contract is enforced by `llm/tests/test_stockfish_adapter_isolation.py`.
If `StockfishAdapter` is ever needed in a live path it must first be brought under
pool management, limit normalization, and score normalization, and the isolation test
must be updated with a documented rationale.

## Guardrails

- Never let the LLM or Android client redefine engine semantics.
- Never change cache-key semantics without regression tests.
- Prefer minimal fixes in normalization, limit resolution, or pool lifecycle over broad rewrites.
