OPERATIONS ADDENDUM: BOUNDED RETRIES

Mode-2 Explanation Quality Control

A1. Purpose of Retries

Retries exist only to improve explanation quality, not correctness or safety.

They are a controlled concession to LLM stochasticity and are strictly bounded.

Retries are not a recovery mechanism for:

rule violations

hallucinations

illegal content

infrastructure failures

A2. When Retries Are Triggered

A retry is triggered only if all of the following are true:

LLM output passed forbidden-pattern validation

Explanation quality score < MIN_QUALITY_SCORE

Remaining retry attempts are available

If any condition is false, retries are not allowed.

A3. When Retries Are NOT Allowed

Retries must never occur for:

Failure Type	Retry
Forbidden pattern detected	❌ NO
Validator assertion failure	❌ NO
Algebraic notation leakage	❌ NO
Checkmate language (CP eval)	❌ NO
LLM runtime error	❌ NO
Missing engine data	❌ NO

These failures must stop execution immediately.

A4. Retry Constraints (Hard Limits)
Parameter	Value
Maximum retries	2
Total attempts	3
Prompt changes	❌ Not allowed
System prompt changes	❌ Not allowed
Temperature changes	❌ Not allowed
Validator bypass	❌ Not allowed

Retries reuse:

the same prompt

the same system instructions

the same engine signal

the same RAG context

Only the model’s stochastic generation differs.

A5. Retry Execution Flow (Operational)
Attempt 1
  ↓
validate_mode_2_negative()
  ↓
score_explanation()
  ↓
score < threshold?
  ├─ NO → return output
  └─ YES
        ↓
Attempt 2
  ↓
(validate → score → telemetry)
  ↓
Attempt 3
  ↓
(validate → score → telemetry)
  ↓
FAIL (hard stop)


No branching.
No special cases.

A6. Telemetry During Retries (RETIRED in PR 13)

Per-attempt quality-score telemetry was previously described here
as feeding ``telemetry/quality_scores.jsonl`` via
``record_quality_score``.  The writer existed but had no callers in
the live pipelines (the retry loops never invoked it), so the file
was never written and the corresponding CI artifact upload was
always empty.

PR 13 (2026-05-15) deleted the dead writer + consumer + upload
step + the THREAT_MODEL § T4 surface that defended it.  When
retry-tracking telemetry is actually wired into the live retry
loops, restore this section alongside a working writer + a
THREAT_MODEL § T4 entry.

Until then, retry telemetry is **not implemented**.  Operators
cannot answer "how often retries occur" or "whether retries
improve quality" from production data — that visibility was
documented but never available.

A7. Expected Operational Behavior
Normal

Most explanations pass on first attempt

Occasional second-attempt success

Rare third-attempt failures

Warning Signs

Many explanations require retries

Scores cluster at the minimum threshold

Retry success rate drops over time

These indicate model degradation, not system failure.

A8. Operator Actions on Retry Failures

If repeated retry failures occur:

Inspect telemetry trends

Verify no recent prompt changes

Re-run positive golden tests

Consider model downgrade or replacement

Do not:

raise retry count

lower quality threshold

weaken validators

A9. Invariant (Memorize This)

Retries may improve phrasing, never correctness, and never safety.

If retries fail, the correct outcome is no output.

A10. Design Rationale (Why This Is Safe)

Bounded retries preserve determinism

Safety gates remain absolute

Quality is improved without prompt mutation

Failure remains explicit and observable

This design ensures retries cannot mask regressions.

End of OPERATIONS addendum: retries