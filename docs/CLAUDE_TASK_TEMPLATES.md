# Claude Task Templates

This file contains standardized prompts for Claude development sessions.

Goals:

- keep tasks narrowly scoped
- prevent architecture drift
- enforce test discipline
- ensure deterministic system behavior

All tasks must follow rules defined in:

- `CLAUDE.md`
- `ARCHITECTURE.md`
- `docs/ARCHITECTURE.md`
- `TESTING.md`
- `docs/TESTING.md`
- relevant `.claude/context/*.md` handbooks

Document mapping for this repo:

- engine integration guidance: `.claude/context/engine.md`
- system pipeline guidance: `.claude/context/pipeline.md`
- API contract guidance: `.claude/context/api.md`
- SECA guidance: `.claude/context/seca.md`

General constraints:

- Engine is the chess source of truth.
- LLM explanations must not override engine evaluation.
- Autonomous RL is prohibited.
- Tests must remain objective.
- Tests must not be weakened to pass.
- Changes should be minimal and localized.

## 1. Engine Bug Fix

Read `CLAUDE.md`, `ARCHITECTURE.md`, and `.claude/context/engine.md`.

Task:
Fix the engine-layer issue described below.

Problem:
[describe engine issue]

Constraints:

- Modify only engine-related code or JNI bridge code if required.
- Do not modify Android UI.
- Do not change API contracts unless absolutely necessary.
- Do not weaken tests.

Required output:

- Root cause
- Files changed
- Tests added or updated
- Commit message draft

## 2. Backend API Fix

Read `CLAUDE.md`, `docs/ARCHITECTURE.md`, and `.claude/context/api.md`.

Task:
Fix the backend/API issue below.

Problem:
[describe API bug]

Constraints:

- Modify only relevant backend routes, services, or schemas.
- Preserve API contracts unless versioning is required.
- Do not modify unrelated engine or Android code.
- Add or update regression tests.

Use:

- `backend-coach-specialist`
- `test-writer`
- `architecture-reviewer`

## 3. Coaching Pipeline Fix

Read `CLAUDE.md`, `.claude/context/pipeline.md`, `.claude/context/api.md`, and the relevant validators under `llm/rag/`.

Task:
Fix the coaching pipeline issue below.

Problem:
[describe issue]

Constraints:

- Engine remains the source of truth.
- LLM only explains engine results.
- Modify only classification logic, schema validation, or related backend code.
- Add regression tests.

Use:

- `backend-coach-specialist`
- `test-writer`
- `architecture-reviewer`

## 4. JNI Bridge Investigation

Read `CLAUDE.md` and `.claude/context/engine.md`.

Task:
Investigate and fix the JNI issue below.

Problem:
[describe JNI mismatch]

Constraints:

- Focus only on JNI bridge and move encoding/decoding.
- Do not perform broad refactors.
- Preserve engine evaluation semantics.
- Add regression tests.

Output:

- Root cause
- Fix summary
- Tests run
- Remaining risk

## 5. Redis Cache Bug

Read `CLAUDE.md`, `.claude/context/engine.md`, and the relevant cache modules under `llm/`.

Task:
Fix the caching issue below.

Problem:
[describe issue]

Constraints:

- Modify only cache key logic, TTL logic, or invalidation logic.
- Do not change engine evaluation semantics.
- Add regression tests verifying cache correctness.

Use:

- `engine-specialist` or `backend-coach-specialist`
- `test-writer`
- `architecture-reviewer`

## 6. Android UI Task

Read `CLAUDE.md`, `.claude/context/api.md`, and the relevant files under `android/`.

Task:
Implement the Android task below.

Task description:
[describe UI change]

Constraints:

- Modify only Android client code.
- Maintain dark theme and professional UX.
- Preserve API contract assumptions.
- Run Android lint/tests after changes.

Output:

- Screens/components changed
- API assumptions
- Checks run
- Commit message draft

## 7. Regression Test Creation

Read `CLAUDE.md` and `docs/TESTING.md`.

Task:
Write regression tests for the issue below.

Issue:
[describe bug]

Constraints:

- Do not fix production code unless required for compilation.
- Reproduce real bug behavior.
- Tests must remain objective.

Use:

- `test-writer`

## 8. API Contract Verification

Read `CLAUDE.md`, `.claude/context/api.md`, and the relevant FastAPI route definitions/tests.

Task:
Verify implementation matches documented API contracts.

Area:
[endpoint or module]

Constraints:

- Prefer reporting mismatches before fixing them.
- Avoid broad refactors.
- Use `architecture-reviewer` before finishing.

Output:

- Mismatches found
- Recommended minimal fix
- Tests/docs needing updates

## 9. Feature Implementation

Read `CLAUDE.md`, `ARCHITECTURE.md`, and the relevant `.claude/context/*.md` files.

Task:
Implement the feature below.

Feature:
[describe feature]

Constraints:

- Keep the change minimal and layer-correct.
- Do not introduce autonomous RL.
- Do not perform broad refactors.
- Add tests for the new behavior.

Use:

- appropriate specialist
- `test-writer`
- `architecture-reviewer`

## 10. Safe Code Review

Read `CLAUDE.md`.

Review the current diff.

Check:

- Architecture compliance
- Contract drift
- Missing tests
- Determinism risks
- Layer violations

Constraints:

- Do not modify files.
- Use `architecture-reviewer`.

Output:

- PASS or FAIL
- Critical issues
- Warnings
- Missing tests
- Recommended fixes

## Daily Compact Template

Use this shorter template for quick tasks.

Read `CLAUDE.md` and relevant docs.

Task:
[one specific task]

Constraints:

- Change only necessary files in the correct layer.
- Do not weaken tests.
- Preserve API contracts.
- Avoid broad refactors.

Use:

- appropriate specialist
- `test-writer`
- `architecture-reviewer`

Return:

- summary
- files changed
- tests run
- commit message draft

## Example Tasks

- Fix JNI bridge move propagation bug.
- Add regression tests for `/coach` severity classification.
- Improve Quick Coach Android card UI.

## Usage

Example CLI usage:

```bash
claude
```

or

```bash
claude -p "Fix JNI bridge move mismatch using template 4 in docs/CLAUDE_TASK_TEMPLATES.md."
```
