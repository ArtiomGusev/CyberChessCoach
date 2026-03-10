System Pipeline Specification

This document describes the complete operational pipeline of the AI Chess Coach system.

The pipeline defines how data moves through the system from:

Android client → backend → engine → coaching → LLM → analytics → training recommendations.

The pipeline must remain:

deterministic

observable

modular

testable

Every stage must produce traceable outputs and events.

Pipeline Overview

High-level system pipeline:

Android Client
      ↓
API Layer
      ↓
SECA Auth
      ↓
Request Normalization
      ↓
Engine Evaluation
      ↓
Evaluation Cache
      ↓
Coaching Logic (SECA Brain)
      ↓
RAG Context Builder
      ↓
LLM Explanation Layer
      ↓
Schema Validation
      ↓
SECA Events Logging
      ↓
SECA Analytics Update
      ↓
Response to Android
1. Android Client Request

The Android application initiates requests for:

position evaluation

coaching feedback

deep chess chat

game completion

training recommendation

Example request:

{
 "fen": "...",
 "played_move": "c4"
}

The request must include sufficient context for deterministic evaluation.

2. API Layer

The API layer is responsible for:

validating request format

routing requests to the correct pipeline

enforcing request schemas

rejecting malformed input

Validation includes:

required fields

correct types

legal chess format

Invalid requests must fail safely.

3. SECA Auth Validation

Protected endpoints require authentication.

Auth layer must:

validate access tokens

attach user identity to request context

reject invalid tokens

Auth failures must be logged via SECA Events.

4. Request Normalization

Incoming requests must be normalized before processing.

Normalization includes:

verifying FEN correctness

validating move legality

converting move notation to internal format

attaching game identifiers

Example normalized object:

{
 "user_id": "...",
 "fen": "...",
 "played_move": "c4",
 "game_phase": "middlegame"
}
5. Engine Evaluation

The normalized request is passed to the engine layer.

Engine responsibilities:

compute best move

calculate evaluation score

optionally generate principal variation

Example engine output:

{
 "best_move": "d4",
 "evaluation": 0.42,
 "depth": 20
}

Engine evaluation is the source of truth.

6. Evaluation Cache

Before invoking the engine, the system should check the evaluation cache.

Cache key example:

FEN + engine_depth + engine_settings

If cached evaluation exists:

return cached result

skip engine call

record cache hit event

7. Coaching Logic (SECA Brain)

The SECA Brain interprets engine results.

Responsibilities:

compare played move with best move

classify mistake severity

determine feedback strategy

decide whether to trigger coaching

Example classification:

{
 "played_move": "c4",
 "best_move": "d4",
 "severity": "blunder",
 "category": "tempo"
}

This stage is deterministic.

8. RAG Context Builder

The RAG system builds contextual input for the LLM.

Sources include:

current position

recent moves

player profile

recurring mistake patterns

training focus

Example RAG context:

{
 "player_rating": 1450,
 "common_mistakes": ["tactics", "time pressure"],
 "game_phase": "middlegame"
}

The RAG context builder must produce consistent outputs for identical inputs.

9. LLM Explanation Layer

The LLM generates human-readable coaching explanations.

The LLM receives:

mistake classification

engine recommendation

RAG context

response mode (quick vs deep)

Example output:

{
 "mistake": "Playing c4 instead of d4",
 "consequence": "White loses central control",
 "better_move": "d4",
 "category": "tempo",
 "severity": "blunder"
}

The LLM must not override engine truth.

10. Schema Validation

LLM responses must be validated.

Validation checks:

required fields exist

valid enums

JSON parsing success

Invalid outputs must trigger:

fallback response

SECA event logging

11. SECA Events Logging

Events must be recorded for observability.

Example events:

engine_eval_completed
coaching_generated
llm_response_generated
training_recommendation_created

Event metadata may include:

user_id

game_id

evaluation_score

severity

12. SECA Analytics Update

Analytics update player profile.

Updates may include:

mistake counts

accuracy metrics

training recommendations

improvement trends

Example analytics update:

{
 "tactical_errors": 12,
 "tempo_mistakes": 5,
 "endgame_accuracy": 0.72
}

Analytics must remain deterministic.

13. Response to Android Client

The final response is sent back to the Android app.

Example coaching response:

{
 "mistake": "Playing c4 instead of d4",
 "consequence": "White loses central control",
 "better_move": "d4",
 "category": "tempo",
 "severity": "blunder"
}

Responses must always follow API contracts.

Game Completion Pipeline

When a game ends:

Android
 ↓
POST /game/finish
 ↓
SECA Events logs game completion
 ↓
SECA Analytics updates player profile
 ↓
SECA Brain generates training recommendation
 ↓
Recommendation stored
 ↓
Android retrieves /next-training
Deep Chat Pipeline

Deep chat uses a slightly different pipeline.

Android chat request
 ↓
API validation
 ↓
Auth validation
 ↓
RAG context builder
 ↓
LLM conversational response
 ↓
Schema validation
 ↓
Events logging
 ↓
Response to Android
Observability Requirements

Every stage should be observable.

Key metrics include:

engine latency

cache hit rate

LLM response latency

API response time

error rate

Monitoring allows early detection of system failures.

Failure Handling

Pipeline failures must degrade gracefully.

Examples:

Engine failure:

return cached result if available

log event

LLM failure:

return fallback coaching message

log event

Database failure:

fail safely

avoid data corruption

Determinism Rules

The following parts must remain deterministic:

engine evaluation

mistake classification

coaching decision logic

analytics updates

recommendation generation

LLM responses may vary in wording but must not change factual conclusions.

Pipeline Testing Requirements

Pipeline tests must validate:

Android request processing

engine integration

coaching classification

LLM schema validation

analytics updates

End-to-end tests must simulate real gameplay scenarios.

Pipeline Evolution Rule

The pipeline must not be modified without:

architectural justification

updated documentation

corresponding tests

This ensures system stability as the project evolves.
