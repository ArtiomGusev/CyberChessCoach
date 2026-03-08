"""Root wrapper for the LLM test runner."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "llm" / "run_all_tests.py"


if __name__ == "__main__":
    raise SystemExit(subprocess.run([sys.executable, str(RUNNER), *sys.argv[1:]]).returncode)
