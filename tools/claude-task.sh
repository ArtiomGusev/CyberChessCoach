#!/usr/bin/env bash
set -euo pipefail

TASK="${*:-}"

if [[ -z "$TASK" ]]; then
  echo "Usage:"
  echo "./tools/claude-task.sh \"task description\""
  exit 1
fi

echo "Starting Claude task..."
echo "Task: $TASK"

claude -p "
Read CLAUDE.md first.

Follow all rules defined in CLAUDE.md and keep the implementation aligned with ARCHITECTURE.md and TESTING.md.

Task:
$TASK

Execution policy:
1. Use Explore or equivalent read-only inspection first to understand the relevant code paths.
2. Summarize the affected modules and propose a minimal plan before editing.
3. Use the appropriate specialist subagent for implementation, the test-writer for tests, and the architecture-reviewer before finishing substantial work.
4. Modify only the necessary files in the correct layer.
5. Do not weaken tests or validators.
6. Run relevant checks and fix failures when possible.
7. If blocked, report the blocker clearly.
8. When everything passes, produce a detailed commit message draft.

Commit message format:

type(scope): summary

Changes:
- ...

Tests:
- ...
"
