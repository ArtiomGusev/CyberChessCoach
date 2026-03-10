AI Chess Coach System Architecture

This document describes the target architecture of the Android AI Chess Coach system.
It defines the system structure, layer responsibilities, data flow, constraints, and implementation principles.

The purpose of the project is to build a stable, adaptive, deterministic chess coaching platform where an Android application is powered by a backend combining:

chess engine analysis

SECA architecture

LLM-based coaching

RAG context building

player analytics

training recommendation logic

The final system must remain:

modular

testable

deterministic in critical decisions

stable in production

adaptive without autonomous reinforcement learning

1. Strategic Product Goal

The project goal is to implement a professional Android chess coaching application that adapts to a specific user through deterministic analytics and coaching logic.

The system must provide:

move and position analysis

real-time short coaching feedback

deep chess chat with contextual awareness

user profile–based training recommendations

structured mistake classification

stable and modern mobile UX/UI

The system is complete only when all layers are implemented by all defined rules, including:

Android frontend

backend pipeline

SECA layers

engine integration

LLM coaching

evaluation system

analytics and profile adaptation

JNI bridge correctness

tests and operational discipline

2. High-Level Architecture
┌──────────────────────────────────────────────────────────┐
│                     Android Client                       │
│  - Chess UI                                              │
│  - Training UI                                           │
│  - Quick Coach Mode                                      │
│  - Deep Chat Mode                                        │
│  - Player profile view                                   │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    API / Server Layer                    │
│  - Request validation                                     │
│  - Auth/session checks                                    │
│  - Endpoint orchestration                                 │
│  - Response shaping                                       │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    Core Pipeline Layer                   │
│  - Game ingestion                                          │
│  - Position evaluation orchestration                       │
│  - Coaching pipeline                                       │
│  - Context assembly                                        │
│  - Result persistence                                      │
└───────┬──────────────────┬──────────────────┬────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌────────────────┐  ┌──────────────────┐
│ Engine Layer  │  │ Intelligence    │  │ Data Layer       │
│ - Engine pool │  │ Layer           │  │ - SQL storage    │
│ - JNI bridge  │  │ - Coaching      │  │ - Cache          │
│ - Eval cache  │  │ - RAG builder   │  │ - Profile data   │
│ - UCI control │  │ - LLM modules   │  │ - Analytics      │
└───────────────┘  └────────────────┘  └──────────────────┘
        │                  │                  │
        └──────────────┬───┴──────────────┬───┘
                       ▼                  ▼
            ┌──────────────────┐  ┌──────────────────┐
            │ SECA Layers      │  │ Monitoring       │
            │ - Auth           │  │ - Logs           │
            │ - Events         │  │ - Health checks  │
            │ - Brain          │  │ - Metrics        │
            │ - Analytics      │  │ - Tracing        │
            └──────────────────┘  └──────────────────┘
3. Architectural Principles
3.1 Determinism first

Critical decisions must be deterministic.

This includes:

engine evaluations

mistake classification

severity classification

recommendation logic

player adaptation logic

LLMs must explain and contextualize decisions, but must not replace deterministic evaluation logic.

3.2 Adaptation without autonomous RL

The system must adapt to the player, but autonomous reinforcement learning is prohibited.

Allowed adaptation sources:

player rating

move accuracy trends

mistake categories

opening tendencies

tactical vs positional weaknesses

historical training outcomes

spaced training logic

deterministic difficulty adjustment

3.3 Incremental evolution

The project should grow through small, verifiable changes.
New modules must fit the architecture instead of bypassing it.

3.4 Objective testing

Every major layer must be testable.
Tests must validate real expected behavior and must never be weakened just to pass.

3.5 Source-of-truth separation

Different layers have distinct authority:

engine = chess strength and position truth

pipeline = orchestration truth

analytics = user progression truth

LLM = explanation and coaching phrasing

SECA = security, integrity, event tracking, coordination boundaries

4. Frontend Architecture
4.1 Android client goals

The Android app must be:

modern

dark-themed

professional

responsive

intuitive

stable

adaptive without RL

It should feel like a polished product rather than a prototype.

4.2 Main Android modules
Chess Board Module

Responsibilities:

render board state

accept moves

show legal interactions

visualize engine or coaching hints when allowed

synchronize with backend results

Training Module

Responsibilities:

present lessons, puzzles, or guided sessions

display mistakes and recommendations

adapt flow to player profile deterministically

Quick Coach Module

Purpose: immediate short coaching feedback.

Characteristics:

concise output

fast response

move-level explanation

low cognitive load

Deep Chat Module

Purpose: GPT-style chess assistant.

Capabilities:

discuss current game

answer theory questions

explain plans and concepts

use game context and player profile context

support follow-up reasoning

Profile Module

Responsibilities:

show player trends

strengths and weaknesses

recent improvement areas

recommended next training focus

Resilience Layer

Responsibilities:

network retry policy

offline-safe behavior where possible

graceful fallback when backend or LLM is unavailable

4.3 Android UI requirements

The application UI must use:

dark theme by default

modern and clean layout

professional typography hierarchy

stable and convenient navigation

adaptive layouts

minimal clutter

The UX should prioritize:

fast access to current game insights

low friction between play and coaching

smooth transition between quick feedback and deeper analysis

5. Backend Architecture

The backend acts as the orchestrator of chess evaluation and coaching logic.

Its responsibilities include:

validating requests

running engine analysis

constructing coaching context

invoking LLM modules

storing events and analytics

returning structured responses to Android

5.1 Main backend components
API Layer

Responsibilities:

endpoint handling

schema validation

auth/session checks

response contracts

rate limiting if needed

Server Pipeline

Responsibilities:

coordinate engine, analytics, and LLM steps

enforce deterministic order of operations

persist results

ensure observability

Coaching Core

Responsibilities:

mistake detection

category classification

severity estimation

recommendation generation

training follow-up decisions

LLM Layer

Responsibilities:

explanation generation

conversational coaching

theory elaboration

context-aware responses

RAG Layer

Responsibilities:

assemble trustworthy context

retrieve user-specific signals

minimize hallucinations

enforce bounded context contracts

Data Layer

Responsibilities:

store games

store events

store player metrics

store coaching results

cache engine evaluations and reusable outputs

6. SECA Architecture

SECA is a core architectural subsystem of the backend.
It provides structure for security, controlled reasoning, observability, and adaptive analytics.

All SECA layers must be implemented according to project rules.

6.1 SECA Auth Layer

Purpose: identity, access, and session integrity.

Responsibilities:

authentication

token generation and validation

session checks

user-scoped access control

secure request boundary enforcement

Rules:

all protected endpoints must pass through auth validation

invalid or expired tokens must fail safely

auth logic must be separately testable

6.2 SECA Events Layer

Purpose: event capture and operational traceability.

Responsibilities:

record game lifecycle events

record training sessions

record coaching requests

record engine calls

record LLM interactions at metadata level

record failures and retries

Examples of tracked events:

game_start

move_submitted

game_finish

next_training_requested

coaching_generated

engine_eval_completed

llm_response_failed

Rules:

events must be timestamped

events must be user-scoped where applicable

events must support analytics and debugging

6.3 SECA Brain Layer

Purpose: central reasoning and coordination layer.

This is the deterministic orchestration brain of coaching.

Responsibilities:

interpret engine outputs

combine analytics with current game state

choose coaching strategy

choose response mode

determine recommendation priority

coordinate between evaluation truth and explanation layer

The Brain layer must not blindly delegate core decisions to the LLM.

It should answer questions such as:

was the move a blunder, mistake, inaccuracy, or acceptable practical choice?

should feedback be immediate or delayed?

should the user get tactical, strategic, or psychological coaching?

what next training type is justified?

6.4 SECA Analytics Layer

Purpose: structured learning analytics and player modeling.

Responsibilities:

track move accuracy trends

classify recurring mistakes

estimate learning progress

track training effectiveness

build deterministic player profile features

support recommendation logic

Example analytics dimensions:

tactical oversight frequency

endgame weakness

opening instability

time pressure error rate

strategic planning gaps

consistency across games

Rules:

analytics should explain player adaptation

analytics must not become opaque or self-modifying

all metrics should be reproducible from stored signals

6.5 Recommended additional SECA extensions

These may be implemented as SECA sublayers or adjacent modules:

SECA Monitoring

service health

latency tracking

engine pool status

failure rates

SECA Safety

prompt injection defenses

output validation

malformed request rejection

secure system prompt isolation

SECA Evaluation Governance

validation of classification logic

drift checks between engine truth and coaching summaries

schema enforcement for LLM outputs

7. Engine Layer

The engine layer is the chess-strength core of the platform.

Responsibilities:

evaluate positions

generate candidate moves

assign scores

support coaching and recommendation logic

7.1 Engine pool

The engine subsystem should support:

multiple engine workers

parallel evaluations where useful

queueing or pooling strategy

controlled resource usage

caching of repeated evaluation requests

Expected properties:

low latency

deterministic settings

reproducible outputs for same inputs under same config

7.2 JNI bridge

The JNI bridge is a critical integration point between Android/native engine components and the higher-level application/backend logic.

Known requirement:
The engine currently may play strongly but not exactly as programmed.
This means the bridge must be investigated and corrected.

Potential fault areas include:

move encoding mismatch

board state desynchronization

incorrect orientation or notation transformation

truncated engine commands

response parsing mismatch

illegal state propagation

UCI handling inconsistency

Validation requirements:

engine-selected move matches expected pipeline result

board states remain synchronized after each move

identical positions produce consistent move results

JNI serialization/deserialization is tested

7.3 Engine source-of-truth rule

The engine determines:

position evaluation

best-move candidates

tactical correctness baseline

The LLM may explain engine results, but must not override them unless an explicitly defined higher-level rule applies and is itself deterministic and tested.

8. LLM Layer

The LLM layer exists to convert structured chess truth into useful human coaching.

It must not become an uncontrolled decision-maker.

8.1 LLM roles

Allowed roles:

explain mistakes

explain better plans

discuss concepts

answer chess questions

adapt phrasing to user profile

generate encouraging or instructional language

Disallowed roles:

changing engine truth

inventing unsupported evaluations

modifying user model arbitrarily

bypassing structured response schemas

introducing autonomous RL-like policy adaptation

8.2 Two-response-mode support
Mode A: Quick response

Used during active play or immediate review.

Requirements:

low latency

short structured message

actionable explanation

consistent phrasing

Mode B: Deep chat

Used for deeper chess dialogue.

Requirements:

multi-turn coherence

game-aware context

player-aware context

topic continuity

bounded hallucination risk through RAG

8.3 LLM structured output

For machine-readable coaching, responses should use strict schemas where required.

Example:

{
  "mistake": "Played c4 instead of d4",
  "consequence": "Gave up central control and slowed development",
  "better_move": "d4",
  "category": "Tempo",
  "severity": "blunder"
}

Rules:

outputs must be validated

unknown fields should be rejected or handled explicitly

missing required fields should fail safely

free-form text should not break pipeline parsing

8.4 Prompt discipline

Prompts must be:

structured

role-separated

minimal but sufficient

context-bounded

safe against user attempts to override system instructions

Prompt inputs may include:

engine result

move sequence

classified mistake

player profile summary

response mode

training objective

Prompt inputs must not include unnecessary raw noise.

9. RAG Architecture

RAG is used to improve factual and personalized coaching.

The purpose is not general retrieval, but controlled contextual grounding.

9.1 RAG sources

Potential retrieval sources:

current game state

previous moves

recent games

player profile summary

recurring mistake patterns

current training objective

historical recommendations

opening repertoire notes

lesson or puzzle history

9.2 RAG design rules

The context builder must be deterministic.

Rules:

same inputs should lead to same context bundle

retrieval must prefer relevance and recency

context window must remain bounded

contradictory signals must be resolved explicitly

retrieval results must be auditable

9.3 RAG output contract

The RAG layer should output structured context objects, not loose text blobs only.

Example structure:

{
  "player_profile": {
    "rating_estimate": 1450,
    "main_weaknesses": ["tactics", "time pressure"],
    "preferred_style": "active"
  },
  "current_game": {
    "phase": "middlegame",
    "mistake_pattern": "missed central break"
  },
  "training_focus": ["calculation", "opening discipline"]
}
10. Coaching and Evaluation System

The coaching system transforms raw engine evaluation into actionable learning.

10.1 Coaching pipeline

Recommended sequence:

receive move or position

validate request

evaluate position with engine

compare played move with stronger candidate(s)

classify mistake or approval

enrich with player analytics

build RAG context

generate LLM explanation

validate output schema

store results and events

return response to Android

10.2 Mistake classification

The coaching layer should classify issues such as:

blunder

mistake

inaccuracy

missed tactic

strategic misplan

opening principle violation

endgame technique issue

tempo loss

king safety issue

calculation failure

This classification must be deterministic and testable.

10.3 Recommendation system

Recommendations should be based on:

recurring error types

game phase weaknesses

current profile trend

recent performance volatility

training history effectiveness

Recommendation examples:

tactical puzzles

opening simplification

endgame drills

visualization/calculation training

positional planning lessons

No autonomous RL-based recommendation policy is allowed.

11. Data Layer

The data layer stores persistent and cached state required for stable operation.

11.1 Main data domains

users

auth/session data

games

moves

engine evaluations

coaching outputs

training sessions

analytics aggregates

model context summaries

operational events

11.2 Storage principles

schema changes require migrations

event and analytic tables should support reproducibility

cache should not become the only source of truth

important derived metrics should be reconstructable

11.3 Cache usage

Caching is useful for:

repeated engine evaluations

repeated derived summaries

repeated context lookups

Cache rules:

cache keys must be explicit

stale data risk must be understood

correctness must not depend on accidental cache behavior

12. Request and Data Flow
12.1 Quick coaching flow
Android move/request
    ↓
API validation + auth
    ↓
game/position normalization
    ↓
engine evaluation
    ↓
mistake classification
    ↓
player analytics lookup
    ↓
RAG context assembly
    ↓
short LLM explanation
    ↓
schema validation
    ↓
event logging + persistence
    ↓
response to Android
12.2 Deep chat flow
Android deep-chat prompt
    ↓
API validation + auth
    ↓
chat mode routing
    ↓
current game + player profile retrieval
    ↓
RAG context construction
    ↓
LLM deep response generation
    ↓
safety and schema validation
    ↓
event logging
    ↓
response to Android
12.3 Training recommendation flow
game finished
    ↓
SECA Events records completion
    ↓
SECA Analytics updates user profile
    ↓
SECA Brain determines next useful training area
    ↓
recommendation object stored
    ↓
Android receives next-training response
13. Testing Architecture

Testing is mandatory before every push.

No push is allowed until all tests pass.

Tests must remain objective and must not be weakened.

13.1 Test categories
Unit tests

For:

classifiers

parsers

scoring helpers

context builders

analytics calculators

auth functions

Integration tests

For:

API to engine flow

API to LLM flow

JNI bridge behavior

database persistence

SECA event propagation

End-to-end tests

For:

Android to backend request lifecycle

game finish to next-training flow

coaching response generation

deep chat contextual response pipeline

Regression tests

For:

known bugs

parsing failures

schema mismatches

engine/JNI desync

prompt formatting issues

Performance tests

For:

engine latency

cache hit behavior

concurrent requests

API responsiveness

13.2 Testing rules

Forbidden:

changing expected results to hide bugs

weakening assertions to force green tests

skipping critical tests before push

redefining pass conditions without justification

Required:

tests should represent real expected behavior

failing tests should lead to fixing code, not lowering standards

each bugfix should add or preserve regression coverage

14. Security and Safety

The project must defend against both conventional and AI-specific failure modes.

14.1 Conventional security

auth validation

input validation

rate limiting where needed

safe token handling

no hardcoded secrets

safe database access patterns

14.2 AI safety

prompt injection resistance

strict separation of system and user instructions

output schema validation

bounded context windows

controlled tool use

no trust in user-provided chess evaluation claims

14.3 Prompt injection rules

User content must never be allowed to:

override system behavior

rewrite coaching policy

change engine truth

bypass structured outputs

disable safety or validation steps

15. Development Workflow

Each development session should follow this sequence:

identify bug, gap, or feature

confirm architectural layer impacted

implement minimal safe change

add or update objective tests

run all relevant tests

verify no rule was violated

commit with detailed session summary

15.1 Commit policy

Commits must be detailed and meaningful.

Each commit should mention:

what changed

why it changed

impacted modules

tests performed

architectural implications if relevant

Example:

fix(coaching-pipeline): validate structured LLM fields and normalize severity mapping

Changes:
- added schema validation for coaching JSON
- normalized severity parsing for unknown values
- fixed mismatch between engine classification and response formatter

Tests:
- coaching schema unit tests
- API integration test for /coach
- regression test for malformed severity field
16. Completion Definition

The project is complete only when all of the following are true:

Android app is stable and polished

dark-themed professional UX/UI is implemented

quick coaching mode works reliably

deep chess chat works with current game and player profile context

backend pipeline is stable

engine pool and caching are operational

JNI bridge is fixed and verified

SECA Auth is implemented

SECA Events is implemented

SECA Brain is implemented

SECA Analytics is implemented

RAG context building works deterministically

LLM explanations are structured and validated

recommendation system is deterministic

no autonomous RL is used

all required tests exist and pass objectively

pushes occur only after passing tests

all architecture rules are respected

The project is not finished if some parts work in isolation but layers remain incomplete, unvalidated, or non-compliant with the rules.

17. Recommended Repository Documents

To keep the repo disciplined, the following documents are recommended alongside this file:

CLAUDE.md

README.md

PROJECT_ARCHITECTURE.md

TESTING.md

API_CONTRACTS.md

ANDROID_UI_GUIDELINES.md

SECA_SPEC.md

LLM_OUTPUT_SCHEMAS.md

ENGINE_INTEGRATION.md

CONTRIBUTING.md

18. Final Architectural Statement

This project is not a generic chess app and not a generic chatbot.

It is a deterministic AI chess coaching platform with:

strong engine-backed analysis

controlled LLM coaching

strict architectural discipline

Android-first product delivery

adaptive user experience without autonomous RL

complete SECA-based backend structure

Every implementation decision must support that direction.
