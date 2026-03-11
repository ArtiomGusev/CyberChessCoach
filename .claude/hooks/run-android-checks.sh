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

run_android_checks() {
  cd "$CLAUDE_PROJECT_DIR/android"
  if [[ -x "./gradlew" ]]; then
    ./gradlew test lint
  else
    cmd.exe /c gradlew.bat test lint
  fi
}

if [[ "${1:-}" == "--full" ]]; then
  if RESULT="$(run_android_checks 2>&1)"; then
    emit_system_message "Android checks passed."
  else
    emit_stop_block "Android checks failed. Fix the Android validation issues before stopping.\n\n$RESULT"
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

if [[ "$FILE_PATH" != android/* ]]; then
  exit 0
fi

if RESULT="$(run_android_checks 2>&1)"; then
  emit_system_message "Android checks passed after editing $FILE_PATH"
else
  emit_system_message "Android checks failed after editing $FILE_PATH\n\n$RESULT"
fi
