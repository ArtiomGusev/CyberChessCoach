CyberChessCoach

CyberChessCoach is a mono-repository containing a complete chess training system composed of:

an Android application (UI + gameplay)

a C++ chess engine (~1800 Elo) acting as the opponent

an LLM-based explanation engine (RAG + Mode-2) that explains positions after moves are played

The system is designed with strict separation of concerns between playing, evaluating, and explaining chess positions.

High-Level Architecture
User
  │
  ▼
Android App (UI)
  │
  ▼
C++ Chess Engine (~1800 Elo)
  │   (plays a move)
  ▼
Final Position (FEN)
  │
  ▼
Stockfish Evaluator (silent, strong)
  │   (JSON evaluation)
  ▼
LLM Explanation Engine (Mode-2)
  │
  ▼
Human-readable explanation

Key principle

Moves are facts.
Evaluations are judgments.
Explanations are commentary.

No component is allowed to blur these roles.

Repository Structure
chesscoach/
├── android/        # Android application (UI, interaction layer)
├── engine/         # C++ chess engine (~1800 Elo opponent)
├── llm/            # LLM explanation engine (RAG + Mode-2)
├── docs/           # Architecture, testing, operations docs
├── .gitignore
└── README.md


Each top-level directory is logically independent and can be reasoned about in isolation.

android/

Contains the Android application:

board UI

move input

opponent interaction

explanation display

The Android app:

does not evaluate positions

does not generate explanations

does not contain chess logic beyond legality

It acts purely as an orchestrator and presentation layer.

engine/

Contains a standalone C++ chess engine (~1800 Elo) that:

plays against the user

selects a single move given a position

has no knowledge of evaluation or explanations

This engine is intentionally weaker than Stockfish to provide a human-like playing experience.

llm/

Contains the LLM explanation system, including:

Stockfish → JSON evaluator

engine signal extraction (ESV)

RAG document retrieval

Mode-2 prompt system

strict validation and golden tests

The LLM:

never suggests moves

never contradicts engine evaluation

never performs chess calculation

only explains what already happened

This guarantees safe, consistent explanations.

Design Invariants (Non-Negotiable)

The opponent engine never explains

Stockfish never plays

The LLM never calculates

Explanations are generated after moves are committed

No component depends on LLM output for decision-making

These invariants are enforced via tests and validators.

Testing Philosophy

The project uses golden tests to lock behavior:

engine signal extraction

RAG retrieval correctness

prompt snapshots

negative tests to forbid illegal explanations

regression tests for explanation quality

See docs/TESTING.md for details.

Status

This repository is actively developed and structured as a closed-source mono-repo.

Historical standalone repositories (e.g. early LLM-only development) are archived and preserved for reference.

License

All rights reserved.
This project is not open source.

See LICENSE for details.

Summary

ChessCoach is built to be:

modular

testable

explainable

resistant to feedback loops

safe against LLM hallucination

The architecture intentionally prioritizes correctness and control over convenience.

End of README.md
