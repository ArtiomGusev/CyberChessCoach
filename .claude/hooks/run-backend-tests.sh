#!/usr/bin/env bash
set -euo pipefail

emit_system_message() {
  local message="$1"
  python - "$message" <<'PY'
import json
import sys

print(json.dumps({"systemMessage": sys.argv[1]}))
PY
}

emit_stop_block() {
  local reason="$1"
  python - "$reason" <<'PY'
import json
import sys

print(json.dumps({"decision": "block", "reason": sys.argv[1]}))
PY
}

normalize_path() {
  local raw_path="$1"
  local path="${raw_path//\\//}"
  local project_dir="${CLAUDE_PROJECT_DIR//\\//}"

  path="${path#./}"
  path="${path#"$project_dir"/}"

  printf '%s' "$path"
}

run_backend_edit_checks() {
  cd "$CLAUDE_PROJECT_DIR"
  case "$1" in
    llm/rag/*)
      python run_all_tests.py
      ;;
    *)
      python -m pytest -q llm/tests
      ;;
  esac
}

run_backend_full_checks() {
  cd "$CLAUDE_PROJECT_DIR"
  python llm/run_quality_gate.py
  python llm/run_ci_suite.py
}

if [[ "${1:-}" == "--full" ]]; then
  if RESULT="$(run_backend_full_checks 2>&1)"; then
    emit_system_message "Full backend checks passed."
  else
    emit_stop_block "Full backend checks failed. Fix the backend validation issues before stopping.\n\n$RESULT"
  fi
  exit 0
fi

INPUT="$(cat)"
FILE_PATH="$(
  printf '%s' "$INPUT" | python -c "import json,sys; data=json.load(sys.stdin); print((data.get('tool_input') or {}).get('file_path', ''), end='')"
)"

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

FILE_PATH="$(normalize_path "$FILE_PATH")"

case "$FILE_PATH" in
  llm/*)
    ;;
  *)
    exit 0
    ;;
esac

if RESULT="$(run_backend_edit_checks "$FILE_PATH" 2>&1)"; then
  emit_system_message "Backend tests passed after editing $FILE_PATH"
else
  emit_system_message "Backend tests failed after editing $FILE_PATH\n\n$RESULT"
fi
