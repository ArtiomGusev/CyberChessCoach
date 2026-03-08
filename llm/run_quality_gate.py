"""Run the stable linting and type-check gates used by CI."""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYLINT_HOME = PROJECT_ROOT / "tmp_logs" / ".pylint"

FORMAT_TARGETS = [
    "run_all_tests.py",
    "llm/cache_keys.py",
    "llm/elite_engine_service.py",
    "llm/engine_eval.py",
    "llm/fen_hash.py",
    "llm/metrics.py",
    "llm/position_input.py",
    "llm/predictive_cache.py",
    "llm/run_all_tests.py",
    "llm/run_ci_suite.py",
    "llm/run_quality_gate.py",
    "llm/rag/contracts/validate_output.py",
    "llm/rag/llm/config.py",
    "llm/rag/llm/fake.py",
    "llm/rag/quality/explanation_score.py",
    "llm/rag/validators/mode_2_negative.py",
    "llm/rag/validators/mode_2_structure.py",
    "llm/rag/validators/sanitize.py",
    "llm/tests/test_engine_eval_limits.py",
    "llm/tests/test_predictive_cache.py",
]

PYLINT_TARGETS = [
    "run_all_tests.py",
    "llm/cache_keys.py",
    "llm/elite_engine_service.py",
    "llm/engine_eval.py",
    "llm/fen_hash.py",
    "llm/metrics.py",
    "llm/position_input.py",
    "llm/predictive_cache.py",
    "llm/run_all_tests.py",
    "llm/run_ci_suite.py",
    "llm/run_quality_gate.py",
    "llm/rag/contracts/validate_output.py",
    "llm/rag/llm/config.py",
    "llm/rag/llm/fake.py",
    "llm/rag/quality/explanation_score.py",
    "llm/rag/validators/mode_2_negative.py",
    "llm/rag/validators/mode_2_structure.py",
    "llm/rag/validators/sanitize.py",
]

MYPY_TARGETS = [
    "run_all_tests.py",
    "llm/fen_hash.py",
    "llm/metrics.py",
    "llm/position_input.py",
    "llm/run_all_tests.py",
    "llm/run_ci_suite.py",
    "llm/run_quality_gate.py",
    "llm/rag/contracts/validate_output.py",
    "llm/rag/llm/config.py",
    "llm/rag/llm/fake.py",
    "llm/rag/quality/explanation_score.py",
    "llm/rag/validators/mode_2_negative.py",
    "llm/rag/validators/mode_2_structure.py",
    "llm/rag/validators/sanitize.py",
]


def run_step(name: str, cmd: list[str], *, env: dict[str, str] | None = None) -> int:
    print(f"=== RUNNING {name.upper()} ===")
    return subprocess.run(cmd, cwd=PROJECT_ROOT, check=False, env=env).returncode


def main() -> int:
    PYLINT_HOME.mkdir(parents=True, exist_ok=True)

    pylint_env = os.environ.copy()
    pylint_env["PYLINTHOME"] = str(PYLINT_HOME)

    steps = [
        (
            "black",
            [sys.executable, "-m", "black", "--check", *FORMAT_TARGETS],
            None,
        ),
        (
            "pylint",
            [sys.executable, "-m", "pylint", "--score=n", *PYLINT_TARGETS],
            pylint_env,
        ),
        (
            "mypy",
            [sys.executable, "-m", "mypy", *MYPY_TARGETS],
            None,
        ),
    ]

    for name, cmd, env in steps:
        code = run_step(name, cmd, env=env)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
