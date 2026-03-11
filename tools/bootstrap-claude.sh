#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$REPO_ROOT"

echo "Bootstrapping Claude repo setup..."

mkdir -p docs
mkdir -p .claude/hooks
mkdir -p .claude/agents
mkdir -p tools

required_files=(
  "CLAUDE.md"
  "docs/CLAUDE_INIT_CHECKLIST.md"
  "docs/CLAUDE_TASK_TEMPLATES.md"
  ".claude/settings.json"
  ".claude/hooks/validate-bash.sh"
  ".claude/hooks/run-backend-tests.sh"
  ".claude/hooks/run-android-checks.sh"
  ".claude/agents/architecture-reviewer.md"
  ".claude/agents/engine-specialist.md"
  ".claude/agents/backend-coach-specialist.md"
  ".claude/agents/android-specialist.md"
  ".claude/agents/test-writer.md"
  "tools/claude-task.sh"
)

missing_files=()
for path in "${required_files[@]}"; do
  if [[ ! -e "$path" ]]; then
    missing_files+=("$path")
  fi
done

if [[ ${#missing_files[@]} -gt 0 ]]; then
  echo "Missing required Claude repo files:"
  printf ' - %s\n' "${missing_files[@]}"
  echo
  echo "This bootstrap script is intentionally non-destructive."
  echo "Restore the missing files from git before using it."
  exit 1
fi

python - <<'PY'
import json
from pathlib import Path

settings = json.loads(Path(".claude/settings.json").read_text(encoding="utf-8"))
hooks = settings.get("hooks", {})
required = {"PreToolUse", "PostToolUse", "Stop"}
missing = sorted(required - set(hooks))
if missing:
    raise SystemExit(f".claude/settings.json is missing hook sections: {', '.join(missing)}")
PY

grep -q '^@.claude/context/architecture.md$' CLAUDE.md
grep -q '^@.claude/context/pipeline.md$' CLAUDE.md
grep -q '^@.claude/context/engine.md$' CLAUDE.md
grep -q '^@.claude/context/seca.md$' CLAUDE.md
grep -q '^@.claude/context/api.md$' CLAUDE.md
grep -q 'Use Explore or equivalent read-only inspection first' CLAUDE.md
grep -q 'Keep-As-Is Verdicts' docs/CLAUDE_INIT_CHECKLIST.md
grep -q '^## First-Pass Workflow$' docs/CLAUDE_TASK_TEMPLATES.md
grep -q 'Use Explore or equivalent read-only inspection first' tools/claude-task.sh

chmod +x .claude/hooks/*.sh
chmod +x tools/claude-task.sh
chmod +x tools/bootstrap-claude.sh

echo
echo "Claude repo setup verified."
echo
echo "Validated:"
echo "- CLAUDE.md imports the repo context files and keeps the Explore-first workflow."
echo "- docs/CLAUDE_INIT_CHECKLIST.md records the keep-as-is verdicts for hooks, agents, and settings."
echo "- docs/CLAUDE_TASK_TEMPLATES.md includes the first-pass Explore-first workflow."
echo "- .claude/settings.json still has PreToolUse, PostToolUse, and Stop hooks."
echo
echo "Next steps:"
echo "1. Start Claude from the repo root: claude"
echo "2. Run /init once and review the CLAUDE.md diff manually."
echo "3. Run /memory and confirm repo-root CLAUDE.md and auto memory are loaded."
echo "4. Start tasks with: Read CLAUDE.md. Use Explore first, summarize affected modules, then propose a minimal plan before editing."
