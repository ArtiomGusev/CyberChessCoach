# CLAUDE.md

@.claude/context/architecture.md
@.claude/context/pipeline.md
@.claude/context/engine.md
@.claude/context/seca.md
@.claude/context/api.md

## Governance Layers

This repository uses six governance layers:

1. `CLAUDE.md` for project rules and delegation.
2. `.claude/context/` for stable architecture knowledge imported at session start.
3. `.claude/settings.json` for permissions and hooks.
4. `.claude/agents/` for role-specialized subagents.
5. `.claude/hooks/` for deterministic enforcement.
6. CI/CD as the final external gate.

## Project Rules

1. Never push before all required validation passes.
2. Tests must remain objective.
3. Autonomous RL implementation is prohibited.
4. Commits must describe changes in detail.
5. The architecture defined in `ARCHITECTURE.md` and `docs/ARCHITECTURE.md` must not be violated.
6. Do not weaken validators, bypass ESV, or allow the LLM to override engine truth.

## Repo Map

- `llm/`: backend coaching, API, RAG, auth, SECA flows, and backend tests
- `android/`: Android client and Gradle validation surface
- `engine/`: native engine code and engine-side experiments
- `docs/`: architecture, testing, operations, and release references
- `.claude/agents/`: project subagents
- `.claude/context/`: imported repo handbooks
- `.claude/hooks/`: deterministic governance hooks

## Subagent Routing

- Use `engine-specialist` for engine pool, UCI, JNI bridge, move normalization, and evaluation semantics.
- Use `backend-coach-specialist` for API routes, coaching pipeline, auth, RAG assembly, and backend integration behavior.
- Use `android-specialist` for Android UI, API client integration, and Gradle-backed validation.
- Use `test-writer` for unit, integration, regression, and contract coverage.
- Use `architecture-reviewer` for read-only compliance review before closing substantial work.

## Required Checks

- Backend edits should trigger backend-safe checks.
- Android edits should trigger Gradle validation.
- Substantial tasks should use `architecture-reviewer` before finishing.
- Finishing a task should trigger the configured stop hooks before Claude exits.

## References

- `ARCHITECTURE.md`
- `docs/ARCHITECTURE.md`
- `TESTING.md`
- `docs/TESTING.md`
