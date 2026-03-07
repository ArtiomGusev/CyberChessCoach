import asyncio

import chess
import pytest

from llm.engine_eval import EngineEvaluator


class _FakeEngine:
    def __init__(self):
        self.limits = []
        self.fens = []

    async def analyse(self, board, limit):
        self.limits.append(limit)
        self.fens.append(board.fen())
        return {
            "score": chess.engine.PovScore(chess.engine.Cp(34), chess.WHITE),
            "pv": [chess.Move.from_uci("e2e4")],
        }


def test_evaluate_with_engine_uses_nodes_limit():
    async def _run():
        evaluator = EngineEvaluator(pool=None)
        engine = _FakeEngine()

        result = await evaluator.evaluate_with_engine(
            engine,
            "startpos",
            movetime=20,
            nodes=4000,
        )

        assert result == {"score": 34, "best_move": "e2e4"}
        assert len(engine.limits) == 1
        assert engine.limits[0].nodes == 4000
        assert engine.limits[0].time is None

    asyncio.run(_run())


def test_evaluate_with_engine_uses_movetime_limit_when_nodes_missing():
    async def _run():
        evaluator = EngineEvaluator(pool=None)
        engine = _FakeEngine()

        result = await evaluator.evaluate_with_engine(
            engine,
            "startpos",
            movetime=20,
            nodes=None,
        )

        assert result == {"score": 34, "best_move": "e2e4"}
        assert len(engine.limits) == 1
        assert engine.limits[0].nodes is None
        assert engine.limits[0].time == pytest.approx(0.02)

    asyncio.run(_run())


def test_evaluate_with_engine_defaults_to_fast_nodes_when_limits_missing():
    async def _run():
        evaluator = EngineEvaluator(pool=None)
        engine = _FakeEngine()

        result = await evaluator.evaluate_with_engine(
            engine,
            "startpos",
            movetime=None,
            nodes=None,
        )

        assert result == {"score": 34, "best_move": "e2e4"}
        assert len(engine.limits) == 1
        assert engine.limits[0].nodes == evaluator.default_nodes
        assert engine.limits[0].time is None

    asyncio.run(_run())


def test_cache_key_ignores_movetime_when_nodes_are_present():
    evaluator = EngineEvaluator(pool=None)

    fast_key = evaluator._cache_key("startpos", movetime=20, nodes=3000)
    slower_key = evaluator._cache_key("startpos", movetime=40, nodes=3000)

    assert fast_key == slower_key


def test_evaluate_with_engine_accepts_moves_input():
    async def _run():
        evaluator = EngineEvaluator(pool=None)
        engine = _FakeEngine()

        result = await evaluator.evaluate_with_engine(
            engine,
            moves=["e2e4", "e7e5", "g1f3"],
            movetime=20,
            nodes=None,
        )

        assert result == {"score": 34, "best_move": "e2e4"}
        assert engine.fens[0] == "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"

    asyncio.run(_run())
