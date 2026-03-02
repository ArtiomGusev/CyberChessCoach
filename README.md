# CyberChessCoach

AI-powered chess training system with strict separation between move generation, evaluation, and explanation.

## Overview

CyberChessCoach is a mono-repository containing:

- **Android App** – UI and gameplay orchestration
- **C++ Chess Engine** – ~1800 Elo opponent
- **LLM Explanation Engine** – RAG-powered explanations with safety guarantees

The system enforces non-negotiable invariants: the opponent never explains, Stockfish never plays, the LLM never calculates.

## Core Architecture

### System Principle

```
Moves are facts.
Evaluations are judgments.
Explanations are commentary.

No component is allowed to blur these roles.
```

### Design Invariants

- ✓ The opponent engine never explains
- ✓ Stockfish never plays
- ✓ The LLM never calculates
- ✓ Explanations generated only after moves are committed
- ✓ No component depends on LLM output for decision-making

## Data Flow

### Complete Journey: User Move → Explanation

```
1. User Input (Android App)
   │ Sends: move in algebraic notation
   │
   ▼
2. Move Legality Check (Android App)
   │ Validates: move is legal on board
   │ Returns: success/error
   │
   ├─ Error → Display error, repeat input
   │
   └─ Success ↓
   │
   ▼
3. C++ Opponent Engine
   │ Input: Board position (FEN)
   │ Process: Search ~1800 Elo strength
   │ Output: Single move
   │
   ▼
4. Board Update (Android App)
   │ Commits both moves
   │ Freezes game state
   │ Converts to FEN
   │
   ▼
5. Stockfish Evaluator (LLM System)
   │ Input: Final position (FEN)
   │ Process: Full analysis at high depth
   │ Output: JSON evaluation
   │   {
   │     "centipawn_loss": 25,
   │     "is_winning": true,
   │     "is_forced_mate": false
   │   }
   │
   ▼
6. Engine Signal Extraction (ESV)
   │ Input: Raw Stockfish JSON
   │ Process: Normalize, coarsen, validate
   │ Output: Trusted signal vector
   │   • No raw scores
   │   • No move lists
   │   • No search metadata
   │
   ▼
7. RAG Document Retrieval
   │ Input: ESV (engine signal)
   │ Process: Deterministic lookup
   │ Output: Contextual documents
   │   • Strategic principles
   │   • Positional patterns
   │   • Tactical concepts
   │
   ▼
8. Prompt Rendering (Mode-2)
   │ Injects (in order):
   │   • System prompt (fixed)
   │   • Engine signal (verbatim)
   │   • RAG context (verbatim)
   │   • FEN
   │   • Optional user query
   │
   ▼
9. LLM Generation
   │ Input: Complete prompt
   │ Process: Language model (untrusted)
   │ Output: Raw text explanation
   │
   ▼
10. Output Validation
    │ Enforced checks:
    │   ✓ No engine mentions
    │   ✓ No move suggestions
    │   ✓ No invented tactics
    │   ✓ Correct mate handling
    │   ✓ Explicit refusal on missing data
    │
    ├─ Validation fails → Error logged, fallback response
    │
    └─ Validation passes ↓
    │
    ▼
11. Android App Display
    │ Shows explanation to user
    │ Ready for next move
```

## Repository Structure

```
CyberChessCoach/
├── android/                 # Android application
│   ├── UI layer (board, input)
│   ├── Game orchestration
│   └── Explanation display
│
├── engine/                  # C++ chess engine
│   ├── Move generation (~1800 Elo)
│   └── Opponent logic
│
├── llm/                     # Explanation system
│   ├── evaluator/          # Stockfish → JSON
│   ├── esv/                # Engine signal extraction
│   ├── rag/                # Document retrieval
│   ├── prompts/            # Mode-2 prompt templates
│   ├── validators/         # Output contracts
│   └── safety/             # Safety enforcement
│
└── docs/                    # Architecture & testing
    ├── ARCHITECTURE.md      # Complete formal spec
    └── TESTING.md           # Test philosophy & examples
```

## Component Responsibilities

### Android App
**What it does:**
- Renders chess board UI
- Accepts user moves
- Validates legality
- Orchestrates game flow
- Displays explanations

**What it never does:**
- Evaluate positions
- Generate explanations
- Calculate variations
- Contain chess logic beyond legality

### C++ Engine
**What it does:**
- Play against the user
- Select one move per position
- Run at ~1800 Elo strength

**What it never knows:**
- Engine evaluations
- LLM-generated explanations
- Opponent skill level
- Game history

### LLM System (llm/)
**What it does:**
- Extract engine signals deterministically
- Retrieve relevant documents
- Render prompts with injected data
- Call LLM as language realizer only
- Validate all outputs before returning

**What it never does:**
- Calculate moves
- Suggest moves
- Contradict engine evaluation
- Reason beyond provided inputs
- Introduce new facts not in documents

## Data Isolation

| Layer | Input Source | Output Type | Trust Level |
|-------|--------------|-------------|------------|
| Stockfish JSON | Evaluator binary | Raw scores, evals | ✓ Trusted |
| Engine Signal (ESV) | Stockfish JSON | Normalized signal | ✓ Trusted |
| RAG Documents | Document store | Textual context | ✓ Trusted |
| Prompt Rendering | Injected data + templates | Complete prompt | ✓ Trusted |
| LLM Output | Language model | Raw explanation | ✗ Untrusted |
| Validators | LLM output | Validated text | ✓ Trusted |

**Key principle:** The LLM is never trusted. All outputs are validated against strict contracts before reaching the user.

## Safety Model (SECA v1)

Enforced at startup via `llm/seca/safety/freeze.py`:

- ✓ No online training
- ✓ No bandit updates
- ✓ No world model learning
- ✓ No background adaptive loops
- ✓ Deterministic runtime

## Testing Philosophy

The project uses layered testing:

- **Golden tests** – Lock behavior of ESV, RAG, prompt snapshots
- **Negative tests** – Forbid illegal explanations
- **Regression tests** – Ensure explanation quality
- **Validator tests** – Fake LLM simulates violations
- **Contract tests** – Prove all safety rules enforced

See `docs/TESTING.md` for details.

## Project Status

- **Development:** Actively developed
- **Structure:** Closed-source mono-repo
- **License:** All rights reserved (see LICENSE.md)
- **Historical:** Early standalone repos archived for reference

## Getting Started

### Installation
```bash
pip install -r requirements.txt
python setup_stockfish.py
```

### Verify Safety
```bash
python verify_safety.py
```

### Run Server
```bash
uvicorn app.server:app --reload
```

### Health Check
```bash
curl http://127.0.0.1:8000/health
```

## Design Philosophy

CyberChessCoach prioritizes:

1. **Correctness** – Invariants enforced via code & tests
2. **Determinism** – All layers except LLM are reproducible
3. **Explainability** – Every explanation is traceable to data
4. **Safety** – Strict contracts on all LLM outputs
5. **Maintainability** – Loose coupling, clear boundaries

Over convenience or feature velocity.

## Further Reading

- **ARCHITECTURE.md** – Formal system specification, trust boundaries, data flow details
- **TESTING.md** – Test strategy, validator rules, test patterns
- **LICENSE.md** – Rights and attribution