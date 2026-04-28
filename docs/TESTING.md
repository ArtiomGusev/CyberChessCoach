TESTING.md
Purpose

This document defines mandatory and optional tests for the ChessCoach-AI Mode-2 system.

Tests exist to guarantee:

correctness

safety

non-hallucination

long-term stability

No test exists to measure chess strength or stylistic quality.

Definitions

Golden test: deterministic test with fixed expected output

Contract test: behavioral constraint on LLM output

Smoke test: basic execution check

Regression test: repeated execution to detect drift

CI: Continuous Integration (GitHub Actions)

Test Categories
Category A — Golden Tests (MANDATORY)

Purpose

Lock deterministic logic

Prevent prompt drift

Prevent retrieval drift

Scope

Engine → ESV mapping

RAG retrieval

Mode-2 prompt injection

Commands

python -m pytest -q llm/rag/tests/golden/test_retriever.py
python -m pytest -q llm/rag/tests/golden/test_prompt_snapshot.py


Rules

Must always pass

Must produce no output on success

Any failure blocks merge

CI

Yes

Category B — LLM Contract Tests (MANDATORY)

Purpose

Enforce LLM behavior rules

Prevent hallucinations

Prevent engine leakage

Scope

Forbidden phrases

Forced-mate handling

Missing-data handling

LLM Used

Fake LLM only

Command

python -m pytest -q llm/rag/tests/contracts/test_fake_llm.py


Rules

Must always pass

Must run in CI

Validators must never be weakened

CI

Yes

Category C — Real LLM Smoke Test (OPTIONAL, LOCAL ONLY)

Purpose

Verify real LLM connectivity

Verify validators accept real output

Scope

Ollama model execution

Output passes contract validators

Command

python -m pytest -q llm/rag/tests/llm/test_ollama_smoke.py


Rules

Must not run in CI

Failure indicates environment or model issue

No golden expectations

CI

No

Category D — LLM Regression Tests (OPTIONAL, LOCAL ONLY)

Purpose

Detect model drift

Detect intermittent violations

Scope

Repeated runs of real LLM

Contract compliance over time

Command

python -m pytest -q llm/rag/tests/llm/test_llm_regression.py


Rules

Must not run in CI

Any failure indicates instability

Validators must not be relaxed to fix failures

CI

No

Category E — Quality Heuristic Tests (OPTIONAL)

Purpose

Detect explanation degradation

Assist human review

Scope

Length heuristics

Sentence structure

Non-triviality

Command

python -m pytest -q llm/rag/tests/quality/test_explanation_quality.py


Rules

Must never block CI

Failures are advisory only

No exact text matching

CI

No

Required Test Runs
Before pushing code
python llm/run_quality_gate.py
python llm/run_ci_suite.py
python -m pytest -q llm/rag/tests/golden/test_retriever.py
python -m pytest -q llm/rag/tests/golden/test_prompt_snapshot.py
python -m pytest -q llm/rag/tests/contracts/test_fake_llm.py
python -m pytest -q llm/tests/test_api_contract_validation.py
python -m pytest -q llm/tests/test_coaching_pipeline_regression.py

Before release (local)
python -m pytest -q llm/rag/tests/llm/test_ollama_smoke.py
python -m pytest -q llm/rag/tests/llm/test_llm_regression.py

CI Policy

CI runs only the following:

python llm/run_quality_gate.py
python llm/run_ci_suite.py
python -m pytest -q llm/rag/tests/golden/test_retriever.py
python -m pytest -q llm/rag/tests/golden/test_prompt_snapshot.py
python -m pytest -q llm/rag/tests/contracts/test_fake_llm.py
python -m pytest -q llm/tests/test_api_contract_validation.py
python -m pytest -q llm/tests/test_coaching_pipeline_regression.py


The golden tests, LLM contract tests, API contract validation, and coaching pipeline
regression tests each run as explicit named steps in the python-tests CI job
(fly-deploy.yml) so that failures are immediately visible in the GitHub Actions UI.
The full suite (run_ci_suite.py) follows as the authoritative coverage gate.

CI quality gates also enforce:

Black formatting checks

Pylint checks on the stable Python surface

Mypy checks on the typed utility surface

Coverage fail-under 80% for the CI-covered Python modules

pip-audit and Trivy security scans


CI must never run:

real LLM tests

regression tests

quality heuristics

Enforcement Rules

Golden failures indicate logic or prompt regressions

Contract failures indicate safety violations

Regression failures indicate model instability

Quality failures indicate possible UX degradation only

No test category may be removed without replacement.

Invariants

If all CI tests pass, the system is guaranteed to be:

deterministic

non-hallucinatory

rule-compliant

regression-protected

Non-Goals

This test suite does NOT:

evaluate chess strength

optimize wording

rank models

measure creativity


LLM Regression Test Frequency (MANDATORY POLICY)
Definition

LLM regression tests are designed to detect behavior drift over time in real language models.

They are not continuous tests and are not CI tests.

Required Frequency

LLM regression tests MUST be run in the following situations:

Before any release

After any system prompt change

After any RAG document content change

After updating or replacing the LLM model

After updating Ollama or model weights

Command:

python -m pytest -q llm/rag/tests/llm/test_llm_regression.py

Prohibited Usage

LLM regression tests MUST NOT be:

Run on every commit

Run in CI

Used to evaluate explanation quality

Used to compare models subjectively

They exist only to detect contract violations.

Failure Interpretation

If an LLM regression test fails:

The model behavior is considered unstable

Validators must NOT be weakened

The failure must be addressed by:

lowering temperature

tightening the system prompt

adjusting RAG phrasing

changing model variant

Ignoring a regression failure is not permitted.

Relationship to Other Tests
Test Type	Frequency
Golden tests	Every commit
Contract tests	Every commit
API contract validation	Every commit
Coaching pipeline regression	Every commit
Regression tests	On change events
Quality tests	On demand
Enforcement Rule

A release is invalid unless LLM regression tests pass immediately prior to release.

Invariant

If LLM regression tests pass at release time, then:

Model behavior is contract-stable

No intermittent hallucinations are present

Production deployment is permitted

Android Instrumented Tests

Host-JVM unit tests cover most of the Android client (`./gradlew :app:testDebugUnitTest`). A separate **instrumented** suite under `android/app/src/androidTest/` runs on a real Android runtime — primarily the Atrium layout-inflation smoke suite, which catches AAPT2 link errors / theme-attribute mismatches / drawable-not-found bugs that host-JVM tests can't see.

To run the instrumented suite end-to-end:

`bash scripts/run_connected_android_tests.sh`

The script verifies the SDK + cmdline-tools install, creates a headless AVD if none exist (`atrium_test`, x86_64 Pixel 5 by default), boots the emulator, runs `./gradlew :app:connectedAndroidTest`, and tears the emulator down on success or failure. Idempotent — re-running with an AVD already created reuses it.

One-time prerequisite: install **Android SDK Command-line Tools (latest)** via Android Studio → Settings → Android SDK → SDK Tools tab. The script's preflight check fails loudly with remediation steps when this is missing.

Override knobs (env vars): `AVD_NAME`, `SYSTEM_IMAGE`, `DEVICE_PROFILE`, `BOOT_TIMEOUT_SECONDS`. Use `--keep-running` to leave the emulator up after tests for iterative debugging.

CI cadence

The instrumented suite runs nightly (03:00 UTC) on GitHub-hosted Ubuntu runners with KVM acceleration via the `.github/workflows/android-instrumented.yml` workflow.  Boots a Pixel 5 AVD on API 36 / x86_64 / google_apis, runs `./gradlew :app:connectedAndroidTest`, and uploads HTML + XML reports as artifacts on every run.  AVD snapshots are cached so the per-run boot cost stays under a minute after the first run on a given cache key.

The workflow also accepts `workflow_dispatch` — a developer iterating on JNI or theme code can trigger an ad-hoc CI run from the Actions tab without waiting for the schedule.

The instrumented suite is **not** part of the per-push pipeline: connectedAndroidTest takes 15-30 minutes end-to-end, and adding it to every push would dominate PR latency for a relatively small marginal coverage win (the host-JVM suite catches most regressions).

End of TESTING.md
