"""Run the stable CI pytest suite with coverage and artifacts."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = PROJECT_ROOT / "tmp_logs"

TEST_TARGETS = [
    "llm/rag/tests/golden/test_retriever.py",
    "llm/rag/tests/golden/test_prompt_snapshot.py",
    "llm/rag/tests/contracts/test_fake_llm.py",
    "llm/rag/tests/contracts/test_mode_2_output.py",
    "llm/rag/tests/test_run_mode_2_additional.py",
    "llm/rag/tests/test_run_mode_2_cascades.py",
    "llm/rag/tests/test_run_mode_2_mate_sanitization.py",
    "llm/rag/tests/test_explanation_score.py",
    "llm/rag/tests/unit/test_input_sanitizer.py",
    "llm/tests/test_engine_response_format.py",
    "llm/rag/tests/unit/test_telemetry_event.py",
    "llm/tests/test_cache_keys.py",
    "llm/tests/test_ci_pipeline.py",
    "llm/tests/test_elite_engine_service.py",
    "llm/tests/test_elite_engine_service_resolve_limits.py",
    "llm/tests/test_engine_eval_fallback_cache.py",
    "llm/tests/test_engine_eval_lru_cache.py",
    "llm/tests/test_engine_eval_limits.py",
    "llm/tests/test_fen_move_cache_key.py",
    "llm/tests/test_host_app.py",
    "llm/tests/test_position_input_build_board.py",
    "llm/tests/test_predictive_cache.py",
    "llm/tests/test_stockfish_adapter_isolation.py",
    "llm/tests/test_seca_layer_boundaries.py",
    "llm/tests/test_coaching_pipeline_regression.py",
    "llm/tests/test_api_contract_validation.py",
    "llm/tests/test_explain_schema_validation.py",
    "llm/tests/test_mistake_analytics.py",
    "llm/tests/test_chat_pipeline.py",
    "llm/tests/test_live_move_pipeline.py",
    "llm/tests/test_historical_pipeline.py",
    "llm/tests/test_engine_eval_benchmark.py",
    "llm/tests/test_api_security.py",
    "llm/tests/test_skill_updater_resilience.py",
    "llm/tests/test_next_training_after_game.py",
    "llm/tests/test_engine_eval_android_contract.py",
    "llm/tests/test_game_finish_db_integration.py",
    "llm/tests/test_engine_pool_exhaustion.py",
    "llm/tests/test_cache_redis_unavailable.py",
    "llm/tests/test_seca_status.py",
]

COVERAGE_TARGETS = [
    "llm.cache_keys",
    "llm.elite_engine_service",
    "llm.engine_eval",
    "llm.metrics",
    "llm.position_input",
    "llm.predictive_cache",
    "llm.rag.contracts.validate_output",
    "llm.rag.llm.fake",
    "llm.rag.quality.explanation_score",
    "llm.rag.validators.mode_2_negative",
    "llm.rag.validators.mode_2_structure",
    "llm.rag.validators.sanitize",
    "llm.rag.validators.explain_response_schema",
    "llm.rag.prompts.input_sanitizer",
    "llm.rag.engine_signal.extract_engine_signal",
    "llm.seca.analytics.logger",
    "llm.seca.analytics.events",
    "llm.seca.analytics.mistake_stats",
    "llm.seca.analytics.training_recommendations",
    # llm.seca.coach.chat_pipeline is intentionally excluded from --cov targets:
    # llm.seca.coach.__init__ imports engine.py which loads numpy via a C extension;
    # coverage pre-loading the package triggers "cannot load module more than once
    # per process" when test_chat_pipeline.py later re-imports it.
    # chat_pipeline.py logic is fully exercised by test_chat_pipeline.py (26 tests).
    "llm.seca.events.storage",
    # llm.seca.coach.live_controller and llm.seca.coach.executor are excluded from
    # --cov targets: llm.seca.coach.__init__ imports engine.py which loads numpy via
    # a C extension; coverage pre-loading the package for instrumentation triggers
    # "cannot load module more than once per process" when the tests later re-import.
    # Their logic is fully exercised by TestPostGameCoachRegressionSuite and
    # TestCoachExecutorStability (22 tests).
    "llm.rag.meta.case_classifier",
    "llm.confidence_language_controller",
    # llm.seca.engines.stockfish.pool is intentionally excluded from coverage targets:
    # the majority of its lines require a live Stockfish process and Redis, which are
    # unavailable in the unit-test environment. The pure logic (FenMoveCache, movetime
    # resolution, fallback) is tested via test_engine_response_format.py.
]


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *TEST_TARGETS,
        *[f"--cov={target}" for target in COVERAGE_TARGETS],
        "--cov-report=term-missing:skip-covered",
        "--cov-report=xml:tmp_logs/coverage.xml",
        "--cov-fail-under=80",
        "--junitxml=tmp_logs/pytest-ci.xml",
    ]

    print("=== RUNNING CI TEST SUITE ===")
    return subprocess.run(cmd, cwd=PROJECT_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
