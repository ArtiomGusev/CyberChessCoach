ChessCoach-AI (Mode-2)

Status: Internal · Closed-Source · Proprietary

Overview

ChessCoach-AI (Mode-2) is a non-calculating chess explanation system.

The system explains:

evaluations

strategic ideas

mistakes

It does not calculate moves, suggest moves, or explore variations.

All objective chess analysis is treated as external ground truth.

Core Properties

Deterministic logic outside the LLM

Explicit trust boundaries

Enforced output contracts

Regression-protected behavior

No hallucinated engine facts

Architecture Summary

High-level flow:

Engine JSON → Engine Signal → RAG Retrieval → Prompt Rendering → LLM → Validators → Output


The LLM is treated as an untrusted component.

Details are defined in ARCHITECTURE.md.

Testing

Testing is mandatory and non-optional.

CI-safe tests
python run_all_tests.py


These tests must pass before any push or release.

Detailed test policies are defined in TESTING.md.

Release Process

Releases are gated by:

golden tests

contract tests

LLM regression tests

manual sanity review

The full release checklist is defined in RELEASE.md.

License

This project is proprietary and closed-source.

See LICENSE for full terms.

Intended Audience

This repository is intended for:

the project owner

authorized collaborators

It is not intended for public distribution.

Non-Goals

This project does not:

provide move recommendations

compete with chess engines

expose public APIs

serve as an open-source framework

End of README.md
