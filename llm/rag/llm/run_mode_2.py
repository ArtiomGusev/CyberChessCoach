from rag.validators.mode_2_negative import validate_mode_2_negative
from rag.quality.explanation_score import score_explanation
from rag.telemetry.quality import record_quality_score
from rag.llm.config import MAX_MODE_2_RETRIES, MIN_QUALITY_SCORE


def run_mode_2(llm, prompt, case_type, engine_signal):
    last_score = None

    for attempt in range(1, MAX_MODE_2_RETRIES + 2):  # initial + retries
        output = llm.generate(prompt)

        # 1. Hard safety gate (NO RETRY if fails)
        validate_mode_2_negative(output)

        # 2. Quality score
        score = score_explanation(
            text=output,
            engine_signal=engine_signal,
        )

        # 3. Telemetry (record every attempt)
        record_quality_score(
            score=score,
            case_type=case_type,
            model=llm.model_name,
        )

        # 4. Accept if good enough
        if score >= MIN_QUALITY_SCORE:
            return output

        last_score = score

        # 5. Retry only if attempts remain
        if attempt > MAX_MODE_2_RETRIES:
            break

    # 6. Hard fail after bounded retries
    raise AssertionError(
        f"Explanation quality too low after {MAX_MODE_2_RETRIES + 1} attempts "
        f"(last score: {last_score})"
    )
