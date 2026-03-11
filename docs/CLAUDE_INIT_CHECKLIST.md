# Claude `/init` Checklist

This checklist keeps `/init` useful without letting it flatten this repo's
existing Claude governance setup into generic defaults.

## Purpose

- Use `/init` once from the repo root to improve `CLAUDE.md`.
- Treat the current repo-specific Claude setup as the source of truth.
- Review every suggested change manually before accepting it.

This repo already has:

- `CLAUDE.md`
- `.claude/context/*.md`
- `.claude/settings.json`
- `.claude/hooks/validate-bash.sh`
- `.claude/hooks/run-backend-tests.sh`
- `.claude/hooks/run-android-checks.sh`
- `.claude/agents/*.md`
- `tools/claude-task.sh`

`/init` should refine repo awareness and workflow hints. It should not replace
the existing hooks, agents, or document map.

## Before `/init`

1. Review the working tree with `git status`.
2. Confirm `CLAUDE.md` still imports:
   - `.claude/context/architecture.md`
   - `.claude/context/pipeline.md`
   - `.claude/context/engine.md`
   - `.claude/context/seca.md`
   - `.claude/context/api.md`
3. Keep these documents authoritative:
   - `ARCHITECTURE.md`
   - `docs/ARCHITECTURE.md`
   - `TESTING.md`
   - `docs/TESTING.md`
   - relevant `.claude/context/*.md` files
4. Keep the hard rules visible near the top of `CLAUDE.md`:
   - engine truth is authoritative
   - LLM explains but does not decide
   - autonomous RL is prohibited
   - tests and validators must not be weakened
   - no push before required validation passes
   - changes should stay minimal and layer-correct
5. Do not let `/init` introduce duplicate document names such as
   `PROJECT_ARCHITECTURE.md`, `SYSTEM_PIPELINE.md`, `ENGINE_INTEGRATION.md`, or
   `API_CONTRACTS.md` unless there is explicit repo-wide migration approval.

## Running `/init`

From the repo root:

```bash
claude
```

Then inside Claude:

```text
/init
```

Review the proposed `CLAUDE.md` diff before accepting any changes.

## Review Checklist

### Rule Preservation

Verify the diff still keeps these constraints explicit:

- Engine output is the chess source of truth.
- The LLM explains but does not override engine truth.
- Autonomous RL implementation is prohibited.
- Tests and validators must not be weakened.
- Required validation must pass before pushing.
- Changes should stay minimal and layer-correct.

### Workflow Preservation

Verify the diff still instructs Claude to:

- read `CLAUDE.md` and relevant context first
- use Explore or equivalent read-only inspection first
- summarize affected modules
- propose a minimal plan before editing
- use `architecture-reviewer` before finishing substantial work

### Reference Preservation

Verify the diff still points at the current repo documents instead of inventing
parallel names:

- `ARCHITECTURE.md`
- `docs/ARCHITECTURE.md`
- `TESTING.md`
- `docs/TESTING.md`
- `.claude/context/architecture.md`
- `.claude/context/pipeline.md`
- `.claude/context/engine.md`
- `.claude/context/seca.md`
- `.claude/context/api.md`

Reject changes that duplicate large sections from those documents into
`CLAUDE.md`.

## Keep-As-Is Verdicts

- `.claude/settings.json`: keep as is. It already has broader safe permissions,
  deny rules for destructive git and secret access, and both backend and Android
  hooks.
- `.claude/hooks/validate-bash.sh`: keep as is. It blocks more destructive
  commands than the generic pack.
- `.claude/hooks/run-backend-tests.sh`: keep as is. It is repo-aware and runs
  backend checks based on edited paths plus a stronger stop-hook suite.
- `.claude/hooks/run-android-checks.sh`: keep as is. It already validates the
  Android layer on edit and stop.
- `.claude/agents/*.md`: keep as is. The existing specialist agents and
  `architecture-reviewer` are more repo-specific than a generic replacement.
- `tools/claude-task.sh`: keep and refine. It already routes work through the
  repo's Claude workflow.

No stale hook paths or missing agent files were found during this review.

## After `/init`

Run:

```text
/memory
```

Confirm:

- the repo-root `CLAUDE.md` is loaded
- auto memory is enabled
- no generic or irrelevant memory entries were created

Then run a read-only validation session:

```text
Read `CLAUDE.md`.
Use Explore first to inspect the relevant code paths.
Summarize the engine, backend/API, coaching pipeline, Android, and SECA layers.
Tell me whether the docs and repo structure are aligned.
Do not modify any files.
```

If Claude misidentifies the layer boundaries or the document map, tighten
`CLAUDE.md` or the relevant `.claude/context/*.md` file instead of adding
duplicate architecture docs.
