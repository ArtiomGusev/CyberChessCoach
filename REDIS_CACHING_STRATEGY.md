Redis Caching Strategy

This document defines how Redis is used in the AI Chess Coach backend to improve performance while preserving determinism, correctness, and observability.

Redis is used to:

reduce redundant engine evaluations

accelerate coaching responses

share cached data across backend instances

handle short-lived coordination data

Redis must never replace authoritative data storage.

The authoritative system of record remains the primary database and engine evaluation pipeline.

1. Core Design Principles

Redis usage must follow the following principles.

Deterministic caching

Cache results must correspond exactly to the inputs that generated them.

This means:

identical inputs must produce identical cache keys

different engine configurations must never share cache entries

normalization versions must be included in keys

Cache must never corrupt truth

Cache may accelerate responses, but must never change the meaning of results.

If the cache becomes inconsistent:

results must be recomputed using the engine

cache entries must be invalidated

Cache transparency

All cache behavior must be observable.

The system must track:

cache hits

cache misses

stale cache usage

cache evictions

2. Redis Role in System Architecture

Redis participates in the pipeline here:

Android Request
      ↓
API Layer
      ↓
Engine Dispatcher
      ↓
Redis Cache Lookup
      ↓
Cache Hit? → Return Result
      ↓
Cache Miss → Engine Worker
      ↓
Result Normalization
      ↓
Cache Store
      ↓
Response

Redis therefore acts as a performance optimization layer between the dispatcher and the engine pool.

3. Redis Deployment Model

Redis should be deployed as a shared service accessible by all backend instances.

Recommended setup:

Backend Instance 1
Backend Instance 2
Backend Instance 3
        ↓
      Redis

This enables:

shared evaluation cache

request deduplication

cross-instance performance optimization

4. Cache Categories

The system may use Redis for several types of cached data.

4.1 Engine evaluation cache

Stores normalized engine results for previously evaluated positions.

Typical use case:

repeated positions

identical FEN queries

repeated coaching analysis

4.2 Coaching result cache

Stores coaching output for previously analyzed moves.

Example scenario:

The same mistake appears in multiple contexts.

Instead of regenerating explanation repeatedly, the system may reuse a cached response if context matches.

4.3 Player context cache

Used for quick retrieval of frequently accessed player profile data.

Example:

player rating estimate

recurring mistake categories

recent analytics summary

4.4 In-flight request coordination

Used to prevent duplicate engine evaluations when multiple identical requests arrive simultaneously.

5. Cache Key Design

Cache keys must be deterministic.

They must include all parameters that affect the result.

Engine evaluation key

Example conceptual key:

engine:eval:{hash}

Where {hash} is computed from:

FEN
engine version
engine depth
threads
hash size
normalization version

Example representation:

engine:eval:9f4ab23c
Coaching result key

Example:

coach:eval:{hash}

Inputs to hash:

FEN
played_move
engine_depth
classification_version
rag_context_version
Player profile cache key

Example:

profile:{user_id}

This key should store a short summary of player analytics.

In-flight request key

Example:

engine:inflight:{hash}

This key exists temporarily while evaluation is in progress.

6. Cache Value Structure

Cache values must contain normalized structured data.

Example engine cache entry:

{
  "best_move": "e2e4",
  "evaluation_cp": 24,
  "mate_score": null,
  "depth": 20,
  "pv": ["e2e4", "e7e5"],
  "engine_version": "stockfish-16",
  "timestamp": 1700000000
}

Example coaching cache entry:

{
  "mistake": "Playing c4 instead of d4",
  "consequence": "White loses central control",
  "better_move": "d4",
  "category": "tempo",
  "severity": "blunder",
  "timestamp": 1700000000
}
7. TTL Strategy

Cache entries must expire eventually to prevent stale results.

Recommended TTL values:

Cache Type	TTL
Engine evaluation	24 hours
Coaching result	12 hours
Player profile summary	5 minutes
In-flight marker	10 seconds

Short TTL for profile cache ensures analytics updates propagate quickly.

8. In-flight Request Deduplication

When multiple identical evaluation requests arrive simultaneously, the system should avoid duplicate engine work.

Deduplication flow
Request arrives
↓
Compute cache key
↓
Check evaluation cache
↓
Cache miss
↓
Check inflight key
↓
If inflight exists → wait briefly
↓
If inflight absent → create inflight key
↓
Perform engine evaluation
↓
Store result
↓
Delete inflight key

This approach ensures that burst requests do not overload the engine pool.

9. Redis Failure Handling

Redis failure must not break the system.

The system must degrade gracefully.

Redis unavailable

Fallback behavior:

skip cache lookup

perform live engine evaluation

log cache failure event

Redis outage must not affect correctness.

Redis timeout

If Redis operations exceed timeout:

bypass cache

proceed with engine evaluation

Timeout must be logged for monitoring.

10. Cache Invalidation Rules

Cache invalidation must occur when:

engine version changes

evaluation normalization logic changes

coaching classification logic changes

schema changes affect stored data

This is typically handled by including version identifiers in cache keys.

11. Observability Metrics

Redis usage must be monitored.

Required metrics:

cache hit rate

cache miss rate

cache write rate

inflight deduplication events

Redis latency

Redis error rate

These metrics allow tuning of TTL and cache design.

12. Security Considerations

Redis must be protected against misuse.

Recommended measures:

authentication enabled

network access restricted

no public exposure

command restrictions if necessary

Cache keys must never include:

raw user tokens

sensitive credentials

unvalidated input

13. Performance Targets

Typical performance goals:

Operation	Target
Redis read	< 2 ms
Redis write	< 5 ms
Cache lookup before engine	< 1 ms

These targets help maintain low-latency coaching responses.

14. Testing Requirements

Redis integration must be tested thoroughly.

Required tests:

Unit tests

cache key generation

TTL assignment

normalization of cached values

Integration tests

cache hit path

cache miss path

inflight deduplication

Redis outage fallback

Load tests

burst traffic behavior

high concurrency cache hits

Redis latency under load

15. Operational Rules

Redis usage must obey the global project rules:

pushes are forbidden before all tests pass

cache must not change engine truth

cache keys must be deterministic

cache logic must remain observable

detailed commits are mandatory

16. Completion Criteria

Redis caching strategy is considered correctly implemented when:

deterministic cache keys exist

inflight deduplication works

cache invalidation is version-aware

Redis outage fallback works

cache metrics are observable

all tests pass

17. Final Statement

Redis caching is a performance accelerator, not a source of truth.

Its purpose is to:

reduce engine load

improve latency

enable horizontal scaling

All correctness guarantees must remain anchored in the deterministic engine and coaching pipeline.
