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
    "llm/rag/tests/unit/test_telemetry_event.py",
    "llm/tests/test_cache_keys.py",
    "llm/tests/test_engine_eval_limits.py",
    "llm/tests/test_elite_engine_service.py",
    "llm/tests/test_host_app.py",
    "llm/tests/test_predictive_cache.py",
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
