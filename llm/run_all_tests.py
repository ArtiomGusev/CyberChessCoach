"""
Unified test runner for ChessCoach-AI.

This script is the ONLY supported way to run multiple test categories together.

Usage:
  python run_all_tests.py              -> CI-safe tests only
  python run_all_tests.py --local      -> CI + local-only tests
  python run_all_tests.py --llm        -> ONLY real-LLM tests
"""

import subprocess
import sys


CI_TESTS = [
    "rag.tests.golden.test_retriever",
    "rag.tests.golden.test_prompt_snapshot",
    "rag.tests.contracts.test_fake_llm",
]

LOCAL_ONLY_TESTS = [
    "rag.tests.llm.test_ollama_smoke",
    "rag.tests.llm.test_llm_regression",
]

QUALITY_TESTS = [
    "rag.tests.quality.test_explanation_quality",
]


def run(module: str):
    print(f"\n=== RUNNING: python -m {module} ===")
    result = subprocess.run(
        [sys.executable, "-m", module],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if result.returncode != 0:
        print(f"\nFAILED: {module}")
        sys.exit(result.returncode)
    print(f"PASSED: {module}")


def main():
    args = set(sys.argv[1:])

    if "--llm" in args:
        print(">>> Running REAL LLM tests ONLY")
        for test in LOCAL_ONLY_TESTS:
            run(test)
        return

    print(">>> Running CI-SAFE tests")
    for test in CI_TESTS:
        run(test)

    if "--local" in args:
        print("\n>>> Running LOCAL-ONLY tests")
        for test in LOCAL_ONLY_TESTS:
            run(test)

        print("\n>>> Running QUALITY tests (advisory)")
        for test in QUALITY_TESTS:
            run(test)


if __name__ == "__main__":
    main()
