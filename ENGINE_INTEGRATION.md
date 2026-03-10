Chess Engine Integration Specification

This document defines how the chess engine is integrated into the AI Chess Coach system.

The engine is the source of chess truth in the platform.

Responsibilities include:

evaluating positions

ranking candidate moves

detecting tactical errors

providing evaluation scores

The engine must operate deterministically and be fully validated through testing.

Engine Architecture

The engine layer includes:

Engine Layer
 ├── Engine Pool
 ├── UCI Controller
 ├── Evaluation Cache
 ├── JNI Bridge
 └── Result Normalization
Engine Pool
Purpose

The engine pool manages multiple engine workers to support parallel analysis.

Advantages:

lower latency

improved throughput

controlled CPU usage

Pool Structure

Example architecture:

EnginePool
 ├── EngineWorker_1
 ├── EngineWorker_2
 ├── EngineWorker_3
 └── EngineWorker_N

Each worker maintains:

engine instance

evaluation state

job queue

Pool Requirements

The engine pool must ensure:

engines remain responsive

jobs are queued correctly

engines do not share corrupted state

failed engine processes are restarted

UCI Controller

The engine must be controlled via the UCI protocol.

Responsibilities include:

sending commands

parsing responses

maintaining synchronization

Required commands
uci
isready
position
go depth
stop
quit
Evaluation Cache

Evaluation results should be cached to reduce redundant engine calls.

Example cache key:

FEN + depth + engine settings

Cache values may include:

evaluation score

best move

candidate lines

Cache Requirements

Cache must:

use explicit keys

support eviction

avoid stale results in critical contexts

Cache must never override engine truth incorrectly.

JNI Bridge

The JNI bridge connects:

Android native engine
to
application logic.

Known Issue

The engine may play strongly but not follow programmed logic.

Possible causes include:

move encoding mismatch

board orientation mismatch

incorrect notation conversion

desynchronized board state

truncated engine responses

Validation requirements

The following tests must exist:

board state synchronization test

move encoding test

engine response parsing test

deterministic evaluation test

Result Normalization

Engine results must be normalized before entering the coaching pipeline.

Example structure:

engine_result
 ├── best_move
 ├── evaluation_score
 ├── principal_variation
 └── depth

Evaluation scores should be standardized.

Example:

centipawns
mate scores
Engine Determinism Rules

The engine must run with fixed configuration:

fixed threads

fixed hash size

fixed depth or time settings

This ensures reproducibility.

Engine Testing Requirements

Required tests:

evaluation reproducibility

move ranking correctness

latency benchmarks

JNI synchronization
