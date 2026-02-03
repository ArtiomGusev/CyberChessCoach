ARCHITECTURE.md
Scope

This document defines the architecture and invariants of the ChessCoach-AI Mode-2 system.

The architecture exists to guarantee:

correctness

determinism

non-hallucination

long-term maintainability

Any change that violates an invariant defined here is invalid.

System Role

ChessCoach-AI Mode-2 is a non-calculating chess explainer.

It:

explains evaluations

explains ideas

explains mistakes

It does not:

calculate moves

suggest moves

explore variations

override engine evaluations

High-Level Data Flow
Stockfish JSON (ground truth)
        ↓
Engine Signal Extraction (ESV)
        ↓
RAG Retrieval (document selection)
        ↓
Prompt Rendering (Mode-2)
        ↓
LLM Generation (untrusted)
        ↓
Output Validation (mandatory)
        ↓
Final Response


No step may be skipped or reordered.

Trust Boundaries
Component	Trust Level
Stockfish JSON	Trusted
Engine Signal (ESV)	Trusted
RAG Documents	Trusted
Prompt Renderer	Trusted
LLM	Untrusted
Output Validators	Trusted

The LLM is never trusted.

Engine Signal (ESV)
Definition

The Engine Signal Vector (ESV) is a normalized, loss-limited representation of engine output.

It is the only engine-derived input allowed downstream.

Properties

Extracted deterministically

No numeric precision beyond coarse bands

No move lists

No search metadata

Forbidden

Raw engine output

Principal variations

Depth, nodes, or scores

RAG Retrieval
Definition

RAG retrieval selects explanatory documents based solely on the ESV.

Rules

Retrieval is deterministic

Conditions are explicit

No semantic search

No embedding similarity

Output

A list of document contents that may be used in explanation.

Prompt Rendering (Mode-2)
Definition

Prompt rendering injects:

system prompt

engine signal (verbatim)

RAG context (verbatim)

FEN

optional user query

Rules

Injection order is fixed

Prompt snapshots are golden-tested

No dynamic prompt rewriting

LLM Layer
Role

The LLM is a language realizer only.

It may:

rephrase

explain

contextualize

It may not:

reason beyond provided inputs

introduce new facts

contradict engine evaluation

LLM Interface

All LLMs must implement:

class BaseLLM:
    def generate(self, prompt: str) -> str


No additional methods are allowed.

Output Validation
Definition

All LLM outputs must pass contract validation before being returned.

Enforced Rules

No engine mentions

No move suggestions

No invented tactics

Correct handling of forced mate

Explicit refusal on missing data

Validation failure is a hard error.

Fake LLM
Purpose

The Fake LLM exists to:

test validators

simulate violations

prove enforcement

It is not optional.

Real LLM Integration
Rules

Real LLMs must be wrapped via BaseLLM

Real LLM outputs must pass the same validators

Real LLM tests must not run in CI

Determinism Guarantees
Layer	Deterministic
ESV extraction	Yes
RAG retrieval	Yes
Prompt rendering	Yes
Validators	Yes
LLM output	No

Non-determinism is isolated to the LLM only.

Failure Handling
Missing Data

If required engine information is missing:

Explanation must explicitly state this

No chess content may be generated

Forced Mate

If evaluation type is mate:

Inevitability must be emphasized

Long-term planning must not be discussed

Test Coverage Mapping
Architecture Layer	Protected By
ESV	Golden tests
RAG	Golden tests
Prompt	Snapshot tests
Validators	Contract tests
LLM behavior	Regression tests

No layer is unprotected.

Change Rules
Allowed Changes

Add new RAG documents

Add new golden cases

Improve explanation wording (within contracts)

Add new LLM adapters

Forbidden Changes

Weakening validators

Bypassing ESV

Prompt mutation at runtime

LLM reasoning beyond inputs

Non-Goals

This architecture does NOT:

evaluate chess skill

compete with engines

provide move recommendations

simulate human calculation

Invariants

If all CI tests pass, the system is guaranteed to:

never hallucinate engine facts

never contradict evaluations

never suggest moves

remain regression-safe

End of ARCHITECTURE.md