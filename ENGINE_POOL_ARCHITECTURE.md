Engine Pool Architecture Specification

This document defines the architecture, rules, and operational behavior of the chess engine pool used by the AI Chess Coach backend.

The engine pool is responsible for providing:

fast position evaluation

deterministic move analysis

scalable concurrent processing

reliable engine isolation

stable integration with the coaching pipeline

The engine pool is a core backend subsystem because engine output is the source of chess truth in the platform.

1. Strategic Purpose

The engine pool exists to solve four core problems:

provide low-latency engine analysis for gameplay and coaching

support concurrent requests from Android clients and backend jobs

isolate engine processes to avoid state corruption

make evaluation reproducible under fixed settings

The pool must support both:

interactive low-latency requests

batch or background-style internal analysis during request processing

The pool must remain deterministic, observable, and testable.

2. Core Principles
2.1 Engine is the chess source of truth

The engine determines:

best move

evaluation score

candidate move ranking

tactical correctness baseline

LLM and coaching modules may explain engine output, but they must not override it.

2.2 Determinism first

The engine pool must produce reproducible results under the same inputs and same configuration.

Determinism depends on:

fixed engine version

fixed options

fixed thread count per worker

fixed hash size per worker

fixed search mode

fixed normalization logic

2.3 Worker isolation

Each worker must be isolated from other workers.

A worker must not leak:

board state

search history

corrupted subprocess state

partial command streams

Each request must fully define its position.

2.4 Explicit orchestration

Requests must be scheduled, executed, normalized, and logged explicitly.

No hidden fallback logic should exist that changes correctness without observability.

3. High-Level Architecture
Client / Backend Request
        ↓
Engine API Layer
        ↓
Engine Dispatcher
        ↓
Request Queue
        ↓
Available Engine Worker
        ↓
UCI Controller
        ↓
Engine Process
        ↓
Raw Engine Output
        ↓
Result Normalizer
        ↓
Evaluation Cache
        ↓
Response to Pipeline
4. Main Components

The engine subsystem contains the following components:

Engine Pool
 ├── Dispatcher
 ├── Request Queue
 ├── Engine Workers
 ├── UCI Controllers
 ├── Result Normalizer
 ├── Evaluation Cache
 ├── Health Monitor
 └── Metrics / Logging
5. Dispatcher
Purpose

The dispatcher is responsible for routing evaluation requests to engine workers.

It decides:

whether cached data can satisfy the request

whether a worker is immediately available

whether a request must wait in queue

whether a failed worker must be bypassed

Responsibilities

The dispatcher must:

accept normalized engine requests

compute cache keys

check cache before scheduling work

assign requests to workers

track request lifecycle

enforce latency and timeout policies

Dispatcher rules

The dispatcher must not:

modify engine truth

invent fallback evaluations

silently lower search parameters without logging

reuse stale worker state

All nonstandard behavior must be observable.

6. Request Queue
Purpose

The queue absorbs bursts of demand and provides controlled engine access.

This protects the system from:

overload

worker starvation

process thrashing

latency instability

Queue behavior

Requests should be classified by priority.

Recommended priority classes:

P1 interactive gameplay evaluation

P2 quick coaching feedback

P3 post-game analysis

P4 analytics recomputation or non-urgent internal tasks

Priority must be implemented carefully so urgent requests do not wait behind heavy batch jobs.

Queue requirements

The queue must support:

bounded size

request timeout tracking

cancellation where applicable

fairness across users

visibility into queue depth

Queue failure policy

If the queue is saturated, the system must fail transparently.

Allowed behavior:

return service busy error

degrade non-critical requests

reject lowest-priority work

Forbidden behavior:

returning fabricated evaluation

silently dropping requests without logging

changing engine settings without traceability

7. Engine Workers
Purpose

Workers are long-lived engine execution units.

Each worker contains:

one engine subprocess

one UCI controller

local runtime state

health metadata

Worker lifecycle

Recommended worker lifecycle:

spawn
↓
uci handshake
↓
isready confirmation
↓
idle pool state
↓
receive request
↓
position setup
↓
search
↓
result parse
↓
cleanup/reset
↓
idle pool state
Worker requirements

Each worker must:

respond to uci

respond to isready

support position

support go depth or approved time-based mode

support controlled stop and restart

be restartable after failure

Worker reset rule

Between requests, worker state must be treated as unsafe unless explicitly reset.

At minimum, each request must re-send:

position

move list if needed

search command

If a worker becomes inconsistent, it must be recycled.

8. UCI Controller
Purpose

The UCI controller is the strict protocol boundary between the application and the engine subprocess.

It is responsible for:

command serialization

stdout parsing

response synchronization

timeout handling

Required commands

Core command support must include:

uci
isready
ucinewgame
position fen ...
position startpos moves ...
go depth N
stop
quit

Optional support may include:

setoption name Threads value X
setoption name Hash value Y
go movetime T
UCI safety rules

The UCI controller must:

serialize commands correctly

avoid interleaving request streams

parse bestmove reliably

parse info lines consistently if used

enforce timeouts

It must not assume partial engine output is valid final output.

9. Result Normalizer
Purpose

Raw engine output is not returned directly to higher layers.

The normalizer converts raw engine output into a stable internal structure.

Normalized output example
{
  "best_move": "e2e4",
  "evaluation_cp": 24,
  "mate_score": null,
  "depth": 20,
  "pv": ["e2e4", "e7e5", "g1f3"],
  "source": "engine"
}
Normalization responsibilities

The normalizer must:

convert score format into internal standard

separate centipawn vs mate values

normalize move format

attach source metadata

reject malformed engine output

Score normalization

Scores should be stored in a structured form.

Recommended internal model:

evaluation_cp: integer or null

mate_score: integer or null

perspective: engine side or normalized player side

depth: integer

Avoid mixing centipawn and mate data in one ambiguous numeric field.

10. Evaluation Cache
Purpose

The cache avoids redundant engine work for repeated positions.

It reduces:

latency

CPU usage

duplicate analysis load

Cache key design

Cache keys must be explicit and deterministic.

Recommended key inputs:

FEN

engine version

depth or search mode

relevant engine settings

normalization version

Example conceptual key:

hash(FEN + depth + engine_version + threads + hash_size + normalization_version)
Cache value

Cache entries may contain:

best move

normalized evaluation

principal variation

search depth

source metadata

timestamp

Cache rules

The cache must:

never mix outputs from incompatible engine settings

be invalidated when engine version changes

distinguish different search depths

expose cache hit metrics

Cache policy

Recommended policy:

Redis for shared cache

optional in-memory cache for per-process hot entries

TTL based on workload profile

deterministic keys only

For correctness-critical endpoints, stale handling must be explicit.

11. Health Monitor
Purpose

The monitor tracks worker health and system readiness.

It ensures that the pool can detect and respond to:

hung processes

bad UCI state

repeated parse errors

high latency

worker crashes

Health checks

A worker should be considered healthy if it:

completed UCI handshake

responds to isready

completes evaluations within policy

returns parseable output

Health actions

When a worker becomes unhealthy, the system should:

mark worker unavailable

stop accepting new jobs for it

restart the worker

log failure cause

expose metrics and events

12. Metrics and Observability

The engine pool must be observable.

Required metrics include:

active workers

total worker capacity

queue depth

average eval latency

p95 eval latency

timeout count

crash count

cache hit rate

restart count

Example health response integration

The /health endpoint should expose at least:

{
  "status": "ok",
  "engine_pool_available": 2,
  "engine_pool_capacity": 2,
  "redis_available": true
}

Additional internal metrics may include:

average queue wait time

worker restart frequency

invalid parse count

13. Request Types

The engine pool should support several request types.

13.1 Single position evaluation

Used for:

quick coach

gameplay evaluation

current move comparison

13.2 Candidate move analysis

Used for:

richer coaching

best move alternatives

recommendation context

13.3 Full game batch analysis

Used for:

post-game review

analytics recomputation

training recommendation input

These requests should not starve real-time traffic.

14. Latency Targets

Latency targets should be realistic and tied to endpoint type.

Recommended goals:

/engine/eval cached: under 20 ms server-side

/engine/eval live low-depth interactive: under 100 ms server-side

/coach/quick: under 300 ms total server-side where feasible

heavy full-game analysis: handled as bounded synchronous pipeline work with explicit cost expectations

Actual targets depend on hardware and engine settings, but must be measured continuously.

15. Scaling Model

The engine pool must scale horizontally and vertically.

Vertical scaling

Increase:

number of workers per host

CPU allocation

memory for hash and cache

Constraints:

too many workers can reduce performance from CPU contention

hash memory must remain bounded

Horizontal scaling

Add more backend instances, each with:

local worker pool

shared Redis cache

shared database/event pipeline

This model allows scaling to many users while preserving deterministic request contracts.

16. Redis Caching Strategy

Redis is recommended as the shared cache layer.

Benefits

shared cache across instances

reduced duplicate evaluations

fast lookup

useful for burst traffic

Recommended Redis usage

Use Redis for:

normalized engine result cache

short-lived request deduplication markers

possibly queue-related operational stats

Do not use Redis as the only persistent source of record for evaluations that matter historically.

Suggested Redis key groups

Example naming approach:

engine:eval:{hash}
engine:pv:{hash}
engine:inflight:{hash}
In-flight deduplication

If multiple identical requests arrive simultaneously, the system may deduplicate them.

Safe pattern:

first request marks evaluation as in-flight

later identical requests wait briefly or reuse final shared result

completed result stored once in cache

This reduces duplicate engine work during bursts.

17. Failure Modes

The architecture must explicitly handle failure.

Worker crash

Response:

restart worker

requeue job if safe

log crash event

UCI desync

Response:

mark worker unhealthy

recycle process

record parsing or sync error

Timeout

Response:

stop search if possible

mark request failed or retry per policy

emit timeout metrics

Redis unavailable

Response:

continue with live evaluation if possible

mark cache as degraded

expose health signal

Full pool saturation

Response:

queue within limits

reject excess low-priority work

preserve responsiveness for interactive requests

18. JNI Bridge Relationship

If native engine integration is used with Android or native components, the engine pool specification must remain consistent with JNI behavior.

Known critical issue:

engine may play strongly but not according to programmed logic

This suggests potential inconsistency between:

requested move path

encoded move

board state

returned best move

interpretation layer

The pool must not assume JNI-originated data is correct without validation.

JNI validation requirements

Tests must verify:

identical position yields identical best move across interfaces

move encoding matches backend normalization

board state stays synchronized across engine calls

no notation conversion bug changes engine meaning

19. Security and Safety

While the engine pool is not an LLM subsystem, it still requires safety boundaries.

The pool must protect against:

malformed FEN input

illegal moves

request flooding

resource exhaustion

command injection into subprocess layers

All UCI command construction must be controlled and sanitized.

20. Testing Requirements

No push is allowed unless all engine-related tests pass.

Required test categories:

Unit tests

cache key generation

result normalization

score conversion

request validation

Integration tests

dispatcher to worker flow

UCI handshake

engine eval request lifecycle

Redis cache interaction

Regression tests

repeated FEN consistency

timeout handling

malformed output parsing

JNI move mismatch bug reproduction

Performance tests

average latency under load

p95 latency

concurrent request handling

queue stability under bursts

Recovery tests

worker crash restart

Redis outage degraded mode

stuck worker recycling

21. Recommended Internal Interfaces

The engine subsystem should expose clear internal contracts.

Evaluation request

Example fields:

{
  "fen": "string",
  "depth": 20,
  "request_type": "interactive",
  "allow_cache": true
}
Evaluation response

Example fields:

{
  "best_move": "e2e4",
  "evaluation_cp": 24,
  "mate_score": null,
  "depth": 20,
  "pv": ["e2e4", "e7e5"],
  "source": "engine",
  "cache_hit": false
}
22. Operational Rules

The engine pool must obey these project-wide rules:

autonomous RL is prohibited

pushes are forbidden before all tests pass

tests must remain objective

worker behavior must remain deterministic

engine settings changes must be documented

detailed commits are mandatory after meaningful development sessions

23. Recommended Deployment Model

For a typical production deployment:

Backend Instance
 ├── API server
 ├── Engine dispatcher
 ├── N engine workers
 ├── local metrics exporter
 └── Redis client

Shared Services
 ├── Redis
 ├── SQL database
 └── central logs / monitoring
24. Completion Criteria

The engine pool architecture is considered properly implemented only when all of the following are true:

workers are isolated and restartable

UCI flow is stable

evaluation normalization is deterministic

Redis/shared cache works correctly

queue behavior is observable

health metrics are exposed

failure recovery is tested

JNI consistency issues are addressed or isolated

all relevant tests exist and pass

25. Final Statement

The engine pool is not just a performance optimization.

It is a foundational subsystem that guarantees:

chess correctness

latency discipline

backend stability

scalable coaching support

reproducible analysis

Every change to this subsystem must be treated as architecture-sensitive and must be accompanied by tests, documentation updates, and detailed commits.
