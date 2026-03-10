CI/CD Pipeline Specification

This document defines the continuous integration and continuous delivery rules for the AI Chess Coach system.

The CI/CD pipeline exists to guarantee that every change entering the project is:

tested

reproducible

reviewable

deployable

traceable

This pipeline is part of the project architecture, not just an operational convenience.

It must enforce the project’s core rules:

never push before all tests pass

tests must remain objective

autonomous RL is prohibited

changes must preserve deterministic behavior in critical layers

detailed commits are mandatory

1. Strategic Purpose

The CI/CD pipeline must ensure that the project evolves safely while supporting continuous development across:

Android frontend

backend API

SECA layers

engine pool

LLM coaching pipeline

Redis caching

database-backed analytics

deployment infrastructure

The pipeline must prevent unstable code, untested changes, and architecture drift from entering the main branch.

2. Core Principles
2.1 Test-gated development

No code may be merged or deployed unless required tests pass.

This rule is absolute.

2.2 Objective validation

The pipeline must validate real expected behavior.

It must not be designed merely to produce green checks.

Forbidden practices include:

disabling failing tests to allow merge

weakening assertions to make tests pass

modifying expected outputs to match broken logic

skipping critical integration checks

2.3 Reproducibility

Builds must be reproducible across environments.

This includes:

pinned dependencies where appropriate

stable Docker builds

deterministic test configuration

fixed engine versions

versioned API and schema contracts

2.4 Incremental safety

The pipeline should fail early when a change introduces risk.

Examples:

schema mismatch

engine integration breakage

JNI regression

invalid API contract

broken structured LLM output parsing

3. Pipeline Scope

The CI/CD process covers:

source validation

code quality checks

backend tests

engine tests

JNI and integration validation

API contract validation

Docker build verification

deployment checks

production rollout

4. Branching and Delivery Model

Recommended branch model:

main — stable production-ready branch

develop — optional integration branch if needed

feature branches — isolated work units

hotfix branches — urgent production fixes

Recommended policy:

all non-trivial changes go through feature branches

main must remain deployable

production deployment should occur only from trusted branch state

5. Commit Policy

Each commit must be meaningful and detailed.

Commits must describe:

what changed

why it changed

impacted modules

tests executed

Example:

fix(engine-cache): separate cache keys by engine depth and normalization version

Changes:
- updated Redis cache key builder
- added normalization_version to cache key
- fixed incorrect cache reuse across depth settings

Tests:
- unit tests for cache key generation
- integration tests for cache hit/miss behavior
- regression test for depth mismatch reuse

Commits like these are preferred over vague messages such as:

fix stuff
update backend
changes
6. Required CI Stages

The pipeline should run in this order.

Stage 1 — Repository integrity checks

Purpose:

validate that the repository is structurally healthy before deeper work begins.

Checks may include:

required files exist

lockfiles are present where expected

migration files are validly named

no obvious secret leaks

docs required for architecture-sensitive changes are present

Stage 2 — Linting and formatting

Purpose:

catch low-cost issues early.

Examples:

Python lint

Kotlin/Android lint

formatting checks

YAML validation

Markdown lint if enforced

This stage should fail quickly.

Stage 3 — Static validation

Purpose:

validate schemas, contracts, and code-level correctness before runtime tests.

Examples:

OpenAPI spec validation

JSON schema validation

typed model checks

dependency graph sanity checks

forbidden-pattern checks

Recommended forbidden-pattern checks include:

hardcoded secrets

debug bypass flags

disabled auth in production code

references to autonomous RL modules

Stage 4 — Unit tests

Purpose:

validate isolated deterministic logic.

Examples:

mistake classification

score normalization

analytics calculations

cache key generation

auth utilities

response schema validation

RAG context assembly rules

These should run on every push and pull request.

Stage 5 — Integration tests

Purpose:

validate subsystem interaction.

Examples:

API to engine flow

API to coaching flow

coaching to LLM schema validator

Redis cache integration

DB persistence

auth and SECA event logging

JNI bridge tests where feasible

Stage 6 — Regression tests

Purpose:

protect against previously observed failures.

This stage must include historical bug reproductions such as:

malformed LLM JSON output

wrong severity parsing

engine cache mismatch

JNI move desynchronization

invalid request normalization

stale evaluation reuse

Every important bug fix should add or update a regression test.

Stage 7 — Performance and latency checks

Purpose:

ensure changes do not silently degrade critical request paths.

Recommended targets:

/engine/eval cached path

/engine/eval live engine path

/coach/quick response path

Redis access timing

queue behavior under burst load

This stage can be lighter on every PR and fuller on protected branches or scheduled runs.

Stage 8 — Docker build verification

Purpose:

confirm deployable artifacts can be built consistently.

Checks should include:

backend image build

any worker/service image build

health command availability

startup command sanity

environment variable requirements

The build must fail if Docker configuration is broken.

Stage 9 — Deployment gating

Purpose:

ensure only valid builds are eligible for deployment.

Deployment must be blocked if any of the following fail:

tests

API contract validation

image build

required migrations

security checks

Stage 10 — Production deployment

Purpose:

deliver tested code to the live environment.

Deployment should include:

image release

startup verification

/health confirmation

basic smoke tests

rollback readiness

7. Backend Test Requirements in CI

The backend pipeline must validate at least the following.

API layer

endpoint request validation

error envelope format

auth enforcement

versioned contract consistency

Engine layer

engine handshake

position evaluation

caching correctness

normalization correctness

timeout handling

Coaching layer

move comparison logic

severity classification

category mapping

structured output validation

SECA layers

auth checks

events persistence

analytics updates

Brain coordination logic

Data layer

migrations

query correctness

persistence integrity

cache/db fallback rules

8. Android Validation in CI

The Android application must also be part of CI validation.

Recommended checks:

project build

lint

unit tests

UI/state handling tests where available

API client contract compatibility

dark theme regressions if screenshot testing exists

The Android client must remain stable, convenient, and adaptive without RL.

9. API Contract Validation

The project uses strict API contracts.

CI must validate:

API_CONTRACTS.md consistency with implementation

OPENAPI_SPEC.yaml validity

response schema compatibility

no undocumented breaking changes

Recommended checks:

OpenAPI lint/validate

generated client compatibility checks

endpoint smoke tests against documented schemas

If implementation and contract differ, CI must fail.

10. LLM Output Validation in CI

Because the project depends on structured coaching responses, CI must validate LLM-facing contracts.

Checks should include:

required fields exist

enum values are valid

malformed responses fail safely

fallback behavior is tested

response parser handles missing or unknown fields correctly

This is critical because your coaching pipeline depends on reliable parsing.

11. Engine and JNI Validation in CI

This project has a known risk around JNI and engine behavior.

CI must include targeted protection for this area.

Required validations:

move encoding correctness

board state synchronization

identical position consistency

normalization agreement between native and backend layers

best move propagation correctness

If the engine plays strongly but not as programmed, the pipeline is not correct. CI must help catch this.

12. Redis and Cache Validation in CI

Redis-based behavior must be tested, not assumed.

Required checks:

cache key determinism

cache hit path

cache miss path

in-flight deduplication behavior

Redis unavailable fallback

version-aware invalidation logic

Cache must improve performance without altering correctness.

13. Database and Migration Validation

Schema changes are high risk and must be validated in CI.

Required checks:

migrations apply successfully on clean DB

migrations apply successfully on existing DB state where relevant

downgrade strategy if supported

required tables and columns exist

ORM models and schema remain aligned

The pipeline must fail on migration drift.

14. Security Checks

CI/CD must include baseline security validation.

Recommended checks:

secret scanning

dependency vulnerability scanning

Docker image scanning

production config sanity checks

forbidden public debug modes

unsafe auth bypass detection

Sensitive data must never be hardcoded or committed.

15. Deployment Environment Rules

Deployment environments should be clearly separated.

Recommended environments:

local development

test/CI

staging

production

Each environment should have:

explicit config

isolated credentials

environment-specific URLs

safe secret handling

Production must not share unsafe debug settings with development.

16. Docker Build Policy

All backend services must be deployable through Docker.

CI must verify:

image builds from clean context

no missing runtime dependencies

container starts correctly

health endpoint is reachable

environment variable assumptions are documented

A Docker build passing locally but failing in CI must be treated as a real issue.

17. Fly.io Deployment Guidance

Since your project has used Fly.io, the pipeline should validate deployment compatibility for that environment.

Recommended checks before Fly deployment:

image builds successfully

startup command is correct

required secrets are configured

health checks pass

release process does not break engine or Redis connectivity

Post-deploy smoke checks should include:

/health

at least one protected endpoint in a safe mode

engine readiness

Redis connectivity where required

18. Smoke Test Stage

After deployment, run a minimal but meaningful smoke suite.

Recommended smoke tests:

GET /health

one engine eval request

one coaching request with known-good input

one DB-backed endpoint

auth check for protected route

Smoke tests should confirm the deployed system is actually usable.

19. Rollback Strategy

The CD pipeline must support rollback or fast recovery.

Rollback triggers may include:

failing smoke tests

startup failure

repeated 5xx on key endpoints

broken engine readiness

critical contract mismatch

Rollback must restore the last known healthy release.

20. Suggested CI Workflow Structure

A practical workflow could look like this:

Push / Pull Request
    ↓
Repository integrity checks
    ↓
Lint / format / static validation
    ↓
Unit tests
    ↓
Integration tests
    ↓
Regression tests
    ↓
API / schema validation
    ↓
Docker build
    ↓
Artifact readiness
    ↓
Merge allowed

For deployment:

Merge to protected branch
    ↓
Full CI suite
    ↓
Docker build and publish
    ↓
Deploy to Fly.io / target environment
    ↓
Health check
    ↓
Smoke tests
    ↓
Release confirmed
21. Recommended GitHub Actions Layout

A useful pipeline may be split into separate workflows:

ci-backend.yml

ci-android.yml

ci-contracts.yml

deploy.yml

ci-backend.yml

Runs:

lint

unit tests

integration tests

regression tests

Docker build check

ci-android.yml

Runs:

Android build

lint

tests

ci-contracts.yml

Runs:

OpenAPI validation

schema checks

contract compatibility tests

deploy.yml

Runs on protected branch or release event:

build/push image

deploy

smoke tests

confirm or rollback

22. Protected Branch Rules

Protected branches should require:

passing CI checks

no failing tests

no direct pushes except controlled cases

review for architecture-sensitive changes

up-to-date branch before merge

At minimum, main should be protected.

23. Pre-Push Local Checklist

Before pushing code, the developer or AI-assisted session should ensure:

all local tests pass

no test was weakened to pass artificially

docs are updated if architecture changed

OpenAPI/API contracts remain valid

Docker build assumptions were not broken

commit message is detailed and session-specific

This local discipline complements CI, it does not replace it.

24. Failure Policy

When CI fails, the correct response is to fix the system, not lower the bar.

Allowed actions:

fix code

fix tests if tests are objectively wrong

fix contracts

fix configuration

Forbidden actions:

disable failing checks to merge faster

change assertions to hide bugs

remove regression coverage without reason

bypass deployment gates

25. Completion Criteria

The CI/CD pipeline is considered correctly implemented only when:

all critical tests run automatically

pushes and merges are gated by test success

Docker builds are validated

API contracts are validated

engine and JNI regressions are covered

Redis/cache behavior is covered

deployment runs smoke tests

rollback or recovery path exists

security checks are included

production deployment is observable

26. Final Statement

CI/CD in this project is not only for automation.

It is a governance system that protects:

architectural integrity

chess correctness

Android stability

backend determinism

API consistency

deployment reliability

Every serious change to the project must pass through this pipeline before it is trusted.
