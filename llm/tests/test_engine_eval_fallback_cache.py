"""
Tests pinning the fallback-caching behaviour of EngineEvaluator.evaluate_with_metrics.

Known behaviour documented here
--------------------------------
When the engine pool is unavailable (empty or timed out), evaluate_with_metrics:
  1. Computes a fast fallback result (first legal move, score=None).
  2. Stores that fallback in the in-memory LRU result cache.
  3. Returns the fallback with engine_fallback=True, engine_result_cache_hit=False.

On the *next* call for the same position and limit parameters:
  4. The LRU cache is hit.
  5. The cached fallback is returned with engine_result_cache_hit=True,
     engine_fallback=False.
  6. The degraded-path origin is now invisible to any caller that relies on
     these flags to decide whether to trust the response.

This is the bug documented in the architecture review. These tests pin the
current behaviour so that any future fix (e.g. tagging cached fallback results
or skipping them on re-evaluation) causes a deliberate test failure and requires
an explicit update to this file.
"""
import asyncio

import chess

from llm.engine_eval import EngineEvaluator


class _EmptyPool:
    """Pool that always reports no engine is available."""

    def acquire_nowait(self):
        return None


class _TrackingPool:
    """Pool that records acquisitions and returns a fake engine on the first call."""

    def __init__(self, fake_engine):
        self._engine = fake_engine
        self.acquire_calls = 0
        self.release_calls = 0

    def try_acquire(self):
        self.acquire_calls += 1
        if self.acquire_calls == 1:
            return self._engine
        return None  # second call: pool empty → fallback

    async def release(self, engine):
        self.release_calls += 1


class _FakeEngine:
    async def analyse(self, board, limit):
        return {
            "score": chess.engine.PovScore(chess.engine.Cp(50), chess.WHITE),
            "pv": [chess.Move.from_uci("e2e4")],
        }


# ---------------------------------------------------------------------------
# Fallback is cached and returned as a cache hit on subsequent calls
# ---------------------------------------------------------------------------

def test_fallback_result_cached_and_returned_as_cache_hit():
    """
    First call: pool empty → fallback stored → engine_fallback=True.
    Second call: same key → LRU hit → engine_result_cache_hit=True, engine_fallback=False.
    The fallback origin is invisible on the second call.
    """
    async def _run():
        evaluator = EngineEvaluator(pool=_EmptyPool())
        evaluator.acquire_timeout_ms = 0

        payload1, metrics1 = await evaluator.evaluate_with_metrics(fen="startpos")

        assert metrics1["engine_fallback"] is True, "First call must return a fallback"
        assert metrics1["engine_result_cache_hit"] is False
        assert payload1["score"] is None, "Fallback has no engine score"
        fallback_move = payload1["best_move"]

        # Second call — same FEN, same resolved limits → same cache key
        payload2, metrics2 = await evaluator.evaluate_with_metrics(fen="startpos")

        assert metrics2["engine_result_cache_hit"] is True, (
            "Second call must hit the LRU cache containing the fallback result"
        )
        assert metrics2["engine_fallback"] is False, (
            "engine_fallback is False on a cache hit — degraded origin is invisible. "
            "If you change this so the flag is preserved, update this assertion."
        )
        assert payload2["best_move"] == fallback_move, (
            "Cached fallback move must be returned unchanged"
        )
        assert payload2["score"] is None, (
            "Cached fallback result still has score=None — no engine evaluation was done"
        )

    asyncio.run(_run())


def test_fallback_result_cached_per_limit_key():
    """
    A fallback result is cached under its resolved limit key.
    A request with different limits misses the cache and gets its own fallback.
    """
    async def _run():
        evaluator = EngineEvaluator(pool=_EmptyPool())
        evaluator.acquire_timeout_ms = 0

        # Request 1: default limits (resolves to default_nodes)
        _, metrics_a = await evaluator.evaluate_with_metrics(fen="startpos")
        assert metrics_a["engine_fallback"] is True

        # Request 2: explicit movetime (different cache key)
        _, metrics_b = await evaluator.evaluate_with_metrics(
            fen="startpos", movetime=50
        )
        assert metrics_b["engine_fallback"] is True, (
            "Different limit params produce a different key, so this is a cache miss "
            "and a new fallback, not a hit from the first request's fallback"
        )

    asyncio.run(_run())


def test_real_engine_result_is_not_confused_with_fallback():
    """
    When the pool returns an engine on the first call, the cached result has
    a real score and the metrics do not report engine_fallback.
    Subsequent calls return the cached real result as a cache hit.
    """
    async def _run():
        pool = _TrackingPool(_FakeEngine())
        evaluator = EngineEvaluator(pool=pool)

        payload1, metrics1 = await evaluator.evaluate_with_metrics(
            fen="startpos", nodes=4000
        )
        assert metrics1["engine_fallback"] is False
        assert metrics1["engine_result_cache_hit"] is False
        assert payload1["score"] == 50

        # Second call: cache hit (engine not acquired again)
        payload2, metrics2 = await evaluator.evaluate_with_metrics(
            fen="startpos", nodes=4000
        )
        assert metrics2["engine_result_cache_hit"] is True
        assert metrics2["engine_fallback"] is False
        assert payload2["score"] == 50
        # Engine was only acquired once
        assert pool.acquire_calls == 1

    asyncio.run(_run())


def test_timeout_fallback_is_also_cached():
    """
    A fallback triggered by pool acquisition timeout is also stored in the LRU
    cache and returned as a cache hit on the next call.
    """
    async def _run():
        class _SlowPool:
            def try_acquire(self):
                return None

            async def acquire(self):
                await asyncio.sleep(0.05)  # Always slower than the timeout
                return "engine"

        evaluator = EngineEvaluator(pool=_SlowPool())
        evaluator.acquire_timeout_ms = 1  # 1 ms timeout → always times out

        _, metrics1 = await evaluator.evaluate_with_metrics(fen="startpos")
        assert metrics1["engine_fallback"] is True

        _, metrics2 = await evaluator.evaluate_with_metrics(fen="startpos")
        assert metrics2["engine_result_cache_hit"] is True
        assert metrics2["engine_fallback"] is False

    asyncio.run(_run())
