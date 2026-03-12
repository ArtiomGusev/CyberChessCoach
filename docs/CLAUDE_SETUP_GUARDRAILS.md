# Claude Setup Guardrails

This document summarizes the active Claude guardrails for this repository.

It exists to answer two questions quickly:

- what prevents Claude from drifting into unsafe repo behavior
- where each guardrail is implemented

## Purpose

This repo uses layered Claude controls rather than a single config file.

The current setup is designed to:

- keep engine truth authoritative
- keep architecture and API boundaries explicit
- block destructive shell actions
- run backend and Android validation automatically
- require a read-only understanding pass before edits
- preserve repo-specific docs, hooks, and agents instead of generic defaults

## Guardrail Layers

### 1. Session Rules

Implemented in:

- `CLAUDE.md`

What it enforces:

- engine is the chess source of truth
- LLM explains but does not override engine truth
- autonomous RL is prohibited
- tests and validators must not be weakened
- changes should stay minimal and layer-correct
- Claude should inspect first, summarize affected modules, propose a minimal
  plan, then edit

### 2. Stable Repo Context

Implemented in:

- `.claude/context/architecture.md`
- `.claude/context/pipeline.md`
- `.claude/context/engine.md`
- `.claude/context/seca.md`
- `.claude/context/api.md`

What it enforces:

- stable architecture and pipeline knowledge loaded with the session
- layer-specific rules for engine, API, SECA, and pipeline behavior
- explicit document map for the repo's real structure

### 3. Claude Permissions and Hooks

Implemented in:

- `.claude/settings.json`

What it enforces:

- allowlist for safe repo commands
- deny rules for destructive git usage and secret-bearing files
- `PreToolUse`, `PostToolUse`, and `Stop` hooks

### 4. Pre-Command Shell Blocking

Implemented in:

- `.claude/hooks/validate-bash.sh`

What it blocks:

- `rm -rf`
- `git push`
- `git reset --hard`
- `git clean -fd`
- `git checkout --`
- `git restore --source`
- access patterns targeting `.env` files or `secrets/`

### 5. Automatic Backend Validation

Implemented in:

- `.claude/hooks/run-backend-tests.sh`

What it does:

- runs backend checks after edits under `llm/`
- runs `python run_all_tests.py` for `llm/rag/*`
- runs `python -m pytest -q llm/tests` for other backend edits
- blocks session stop if full backend checks fail

Full stop-hook backend checks:

- `python llm/run_quality_gate.py`
- `python llm/run_ci_suite.py`

### 6. Automatic Android Validation

Implemented in:

- `.claude/hooks/run-android-checks.sh`

What it does:

- runs Android validation after edits under `android/`
- runs `./gradlew test lint` or `gradlew.bat test lint`
- blocks session stop if full Android checks fail

### 7. Read-Only Architecture Review

Implemented in:

- `.claude/agents/architecture-reviewer.md`

What it enforces:

- architecture compliance
- contract drift detection
- missing test detection
- determinism risk review
- final read-only review before closing substantial work

### 8. Specialist Routing

Implemented in:

- `.claude/agents/engine-specialist.md`
- `.claude/agents/backend-coach-specialist.md`
- `.claude/agents/android-specialist.md`
- `.claude/agents/test-writer.md`
- `.claude/agents/devils-advocate.md`

What it enforces:

- engine work stays in engine boundaries
- backend/pipeline work stays in backend boundaries
- Android work stays in Android boundaries
- tests get explicit authoring attention instead of incidental edits
- adversarial security and edge-case review is available as a dedicated read-only pass

### 9. Operator Checklists

Implemented in:

- `docs/CLAUDE_INIT_CHECKLIST.md`
- `docs/CLAUDE_TASK_TEMPLATES.md`
- `tools/claude-task.sh`
- `tools/bootstrap-claude.sh`

What they enforce:

- `/init` is reviewed manually
- task prompts start with Explore/read-only inspection
- task execution follows the repo-specific workflow
- bootstrap verifies the guardrail setup instead of overwriting it

## Session Startup Pattern

For normal sessions:

1. Start from repo root.
2. Read `CLAUDE.md`.
3. Use Explore or read-only inspection first.
4. Summarize affected modules.
5. Propose a minimal plan.
6. Edit only the correct layer.
7. Use specialist agents and `architecture-reviewer` when appropriate.

For first-time Claude setup in this repo:

1. Run `/init` once.
2. Review the `CLAUDE.md` diff manually.
3. Run `/memory`.
4. Confirm repo-root `CLAUDE.md` and auto memory are loaded.

## Change Policy

When modifying Claude setup in this repo:

- do not replace this setup with a generic Claude pack
- preserve current doc names and `.claude/context/*.md` imports
- keep hooks, agents, and settings repo-specific
- update this document if a guardrail source, hook, or agent changes
- prefer refinement over wholesale replacement
