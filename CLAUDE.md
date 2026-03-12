# CLAUDE.md

@.claude/context/architecture.md
@.claude/context/pipeline.md
@.claude/context/engine.md
@.claude/context/seca.md
@.claude/context/api.md

## Project Rules

1. Engine output is the chess source of truth.
2. The LLM explains, but must not override engine truth or bypass ESV.
3. Autonomous RL implementation is prohibited.
4. Tests must remain objective.
5. Never weaken tests or validators to make them pass.
6. Never push before all required validation passes.
7. Prefer minimal, localized, layer-correct changes.
8. The architecture defined in `ARCHITECTURE.md` and `docs/ARCHITECTURE.md` must not be violated.
9. Commits must describe changes in detail.

## Required Reviews

- Use specialist subagents where appropriate.
- Use `architecture-reviewer` before finishing substantial or cross-layer work.
- Use `devils-advocate` for adversarial security, lifecycle, memory, or interop review when code is risky or externally exposed.
- Preserve API contracts unless docs, tests, and dependent callers are updated together.
- Report blockers explicitly instead of bypassing checks.

## Required Workflow

1. Read this file and the relevant `.claude/context/*.md` handbooks before editing.
2. Use Explore or equivalent read-only inspection first to find the relevant code paths.
3. Summarize the affected modules and propose a minimal plan before making changes.
4. Modify only the necessary files in the correct layer.
5. Run the relevant validation and fix failures when possible.
6. Finish with the required checks for the layers you touched.

## Subagent Routing

- Use `engine-specialist` for engine pool, UCI, JNI bridge, move normalization, and evaluation semantics.
- Use `backend-coach-specialist` for API routes, coaching pipeline, auth, RAG assembly, and backend integration behavior.
- Use `android-specialist` for Android UI, API client integration, and Gradle-backed validation.
- Use `test-writer` for unit, integration, regression, and contract coverage.
- Use `devils-advocate` for hostile-input, security, memory, coroutine/lifecycle, and cross-language boundary audits.
- Use `architecture-reviewer` for read-only compliance review before closing substantial work.

## Required Checks

- Backend edits should trigger backend-safe checks.
- Android edits should trigger Gradle validation.
- Finishing a task should trigger the configured stop hooks before Claude exits.

## Repo Map

- `llm/`: backend coaching, API, RAG, auth, SECA flows, and backend tests
- `android/`: Android client and Gradle validation surface
- `engine/`: native engine code and engine-side experiments
- `docs/`: architecture, testing, operations, and release references
- `.claude/agents/`: project subagents
- `.claude/context/`: imported repo handbooks
- `.claude/hooks/`: deterministic governance hooks

## References

- `ARCHITECTURE.md`
- `docs/ARCHITECTURE.md`
- `TESTING.md`
- `docs/TESTING.md`
- `docs/CLAUDE_SETUP_GUARDRAILS.md`
- `.claude/context/architecture.md`
- `.claude/context/pipeline.md`
- `.claude/context/engine.md`
- `.claude/context/seca.md`
- `.claude/context/api.md`
