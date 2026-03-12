"""
Tests for EliteEngineService._resolve_limits — specifically the fallback path
that activates when the injected evaluator does not expose a resolve_limits method.

Architecture gap documented here
----------------------------------
When evaluator.resolve_limits exists, _resolve_limits delegates to it, which
applies both lower-bound clamping (max(1, ...)) AND upper-bound clamping
(min(max_nodes, ...)).

When evaluator.resolve_limits is absent, the fallback path in
EliteEngineService._resolve_limits applies only max(1, int(...)) — there is no
upper ceiling. An extremely large nodes or movetime value passes through
unclamped.

These tests pin both the correct delegation path and the documented gap in the
fallback path. Any future fix that adds clamping to the fallback must update the
assertion in test_resolve_limits_fallback_omits_upper_clamping and document the
migration.
"""
import asyncio
import os

import pytest

from llm.elite_engine_service import EliteEngineService


# ---------------------------------------------------------------------------
# Evaluator stubs
# ---------------------------------------------------------------------------

class _EvaluatorWithResolveLimits:
    """Evaluator that exposes resolve_limits with explicit upper bounds."""

    default_nodes = 5000
    _MAX_NODES = 10_000
    _MAX_MOVETIME = 500

    def resolve_limits(self, *, movetime, nodes):
        resolved_mt = (
            None if movetime is None
            else min(self._MAX_MOVETIME, max(1, int(movetime)))
        )
        resolved_n = (
            None if nodes is None
            else min(self._MAX_NODES, max(1, int(nodes)))
        )
        if resolved_mt is None and resolved_n is None:
            resolved_n = self.default_nodes
        return resolved_mt, resolved_n

    async def evaluate(self, fen=None, *, moves=None, movetime=None, nodes=None):
        return {"best_move": "e2e4", "score": 32}


class _EvaluatorWithoutResolveLimits:
    """Evaluator that does NOT expose resolve_limits — triggers fallback path."""

    default_nodes = 5000

    async def evaluate(self, fen=None, *, moves=None, movetime=None, nodes=None):
        return {"best_move": "e2e4", "score": 32}


# ---------------------------------------------------------------------------
# Delegation path (evaluator HAS resolve_limits)
# ---------------------------------------------------------------------------

def test_resolve_limits_delegates_to_evaluator_when_available():
    service = EliteEngineService(_EvaluatorWithResolveLimits())
    # Evaluator clamps nodes to 10_000.
    _, nodes = service._resolve_limits(movetime=None, nodes=999_999)
    assert nodes == 10_000, "resolve_limits must be fully delegated to the evaluator"


def test_resolve_limits_delegates_movetime_clamping():
    service = EliteEngineService(_EvaluatorWithResolveLimits())
    movetime, _ = service._resolve_limits(movetime=999_999, nodes=None)
    assert movetime == 500


def test_resolve_limits_delegates_default_nodes_when_both_none():
    service = EliteEngineService(_EvaluatorWithResolveLimits())
    _, nodes = service._resolve_limits(movetime=None, nodes=None)
    assert nodes == _EvaluatorWithResolveLimits.default_nodes


def test_resolve_limits_delegates_floor_clamping():
    service = EliteEngineService(_EvaluatorWithResolveLimits())
    movetime, nodes = service._resolve_limits(movetime=0, nodes=0)
    assert movetime == 1
    assert nodes == 1


# ---------------------------------------------------------------------------
# Fallback path (evaluator does NOT have resolve_limits)
# ---------------------------------------------------------------------------

def test_resolve_limits_fallback_omits_upper_clamping():
    """
    Document: the fallback path applies only max(1, int(...)) — no upper ceiling.
    An extremely large nodes value passes through unclamped.

    This is the documented architecture gap. If you change this to add an upper
    bound, update this assertion to assert the clamped value and document the
    maximum in engine.md and api.md.
    """
    service = EliteEngineService(_EvaluatorWithoutResolveLimits())
    _, nodes = service._resolve_limits(movetime=None, nodes=999_999)
    assert nodes == 999_999, (
        "Fallback path must NOT clamp nodes — this is the documented gap. "
        "If you added upper clamping, update this test with the expected maximum."
    )


def test_resolve_limits_fallback_movetime_unclamped():
    """Fallback path does not clamp movetime either."""
    service = EliteEngineService(_EvaluatorWithoutResolveLimits())
    movetime, _ = service._resolve_limits(movetime=999_999, nodes=None)
    assert movetime == 999_999


def test_resolve_limits_fallback_clamps_zero_values_to_one():
    service = EliteEngineService(_EvaluatorWithoutResolveLimits())
    movetime, nodes = service._resolve_limits(movetime=0, nodes=0)
    assert movetime == 1
    assert nodes == 1


def test_resolve_limits_fallback_clamps_negative_values_to_one():
    service = EliteEngineService(_EvaluatorWithoutResolveLimits())
    movetime, nodes = service._resolve_limits(movetime=-100, nodes=-500)
    assert movetime == 1
    assert nodes == 1


def test_resolve_limits_fallback_uses_evaluator_default_nodes_when_both_none():
    service = EliteEngineService(_EvaluatorWithoutResolveLimits())
    movetime, nodes = service._resolve_limits(movetime=None, nodes=None)
    assert movetime is None
    assert nodes == _EvaluatorWithoutResolveLimits.default_nodes


def test_resolve_limits_fallback_uses_predictive_nodes_when_evaluator_missing_default(
    monkeypatch,
):
    """
    When the evaluator has no default_nodes attribute, the fallback path uses
    self.predictive_nodes (from ENGINE_PREDICTIVE_NODES env var).
    """
    monkeypatch.setenv("ENGINE_PREDICTIVE_NODES", "777")
    monkeypatch.setenv("ENGINE_DEFAULT_NODES", "5000")

    class _BareEvaluator:
        default_nodes = 5000  # required for __init__

        async def evaluate(self, *a, **kw):
            return {"best_move": None, "score": None}

    service = EliteEngineService(_BareEvaluator())
    # Remove default_nodes after construction so the getattr fallback is exercised.
    del _BareEvaluator.default_nodes

    movetime, nodes = service._resolve_limits(movetime=None, nodes=None)
    assert movetime is None
    assert nodes == 777


# ---------------------------------------------------------------------------
# Consistency between paths for the common case
# ---------------------------------------------------------------------------

def test_both_paths_agree_on_explicit_small_values():
    """For reasonable inputs that are within any sensible ceiling, both paths agree."""
    svc_with = EliteEngineService(_EvaluatorWithResolveLimits())
    svc_without = EliteEngineService(_EvaluatorWithoutResolveLimits())

    mt_with, n_with = svc_with._resolve_limits(movetime=100, nodes=3000)
    mt_without, n_without = svc_without._resolve_limits(movetime=100, nodes=3000)

    assert mt_with == mt_without == 100
    assert n_with == n_without == 3000
