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

Use the appropriate specialist subagent for implementation, the test-writer for tests, and the architecture-reviewer before finishing substantial work.

Follow all rules defined in CLAUDE.md and keep the implementation aligned with ARCHITECTURE.md and TESTING.md.

Task:
$TASK

Execution policy:
1. Analyze the repository.
2. Modify only the necessary files.
3. Do not weaken tests or validators.
4. Run relevant checks and fix failures when possible.
5. If blocked, report the blocker clearly.
6. When everything passes, produce a detailed commit message draft.

Commit message format:

type(scope): summary

Changes:
- ...

Tests:
- ...
"
