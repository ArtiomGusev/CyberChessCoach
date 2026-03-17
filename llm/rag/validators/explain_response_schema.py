"""Strict JSON schema for /explain and embedded explain responses.

Defines Pydantic models for structural validation and provides
``validate_explain_response()`` / ``validate_embedded_explain_response()``
as the authoritative validation entry points used at the API boundary.

Design constraints:
- engine_signal is produced exclusively by extract_engine_signal() and is
  never sourced from or modified by LLM output.  The EngineSignalSchema
  enforces this contract structurally.
- validate_explain_response() applies Mode-2 content validators for any
  LLM-generated mode (mode != "SAFE_V1"), providing defence-in-depth on
  top of the per-generation validators already applied in run_mode_2().
- validate_embedded_explain_response() is the equivalent gate for the
  edge-deployment embedded.py path.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator, ValidationError


# ---------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------


class ExplainSchemaError(ValueError):
    """Raised when an /explain response fails schema or content validation.

    At the server layer this propagates as HTTP 500 – a schema failure is a
    server-side programming error, not a client input error.
    """


# ---------------------------------------------------------------
# Inner schemas
# ---------------------------------------------------------------


class EvaluationSchema(BaseModel):
    """Mirrors the 'evaluation' sub-dict produced by extract_engine_signal."""

    type: Literal["cp", "mate"]
    band: Literal["equal", "small_advantage", "clear_advantage", "decisive_advantage"]
    side: Literal["white", "black", "unknown"]


class EngineSignalSchema(BaseModel):
    """Full engine signal structure as produced by extract_engine_signal().

    This schema is authoritative.  Any response whose engine_signal does not
    conform to this model is rejected before it reaches the Android client.
    Engine evaluation values are never sourced from LLM output.
    """

    evaluation: EvaluationSchema
    eval_delta: Literal["increase", "decrease", "stable"]
    last_move_quality: str
    tactical_flags: list[str]
    position_flags: list[str]
    phase: Literal["opening", "middlegame", "endgame"]

    @field_validator("tactical_flags", "position_flags")
    @classmethod
    def validate_string_lists(cls, v: list) -> list:
        if not all(isinstance(item, str) for item in v):
            raise ValueError("all items must be strings")
        return v


# ---------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------


class ExplainResponse(BaseModel):
    """Schema for the POST /explain API response.

    engine_signal is produced exclusively by extract_engine_signal() and must
    pass EngineSignalSchema validation.  explanation is a plain string; it may
    be empty for SAFE_V1 (deterministic safe explainer path) but must be
    non-empty and Mode-2 compliant for all LLM-generated modes.
    """

    explanation: str
    engine_signal: EngineSignalSchema
    mode: str


class EmbeddedExplainResponse(BaseModel):
    """Schema for the embedded explain_position() API response.

    Used by the edge deployment (llm/rag/deploy/embedded.py).  confidence must
    be exactly 'high' or 'low' – no other values are valid contract-wise.
    """

    explanation: str
    confidence: Literal["high", "low"]
    tags: list[str]

    @field_validator("explanation")
    @classmethod
    def explanation_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("explanation must be non-empty")
        return v

    @field_validator("tags")
    @classmethod
    def tags_must_be_strings(cls, v: list) -> list:
        if not all(isinstance(t, str) for t in v):
            raise ValueError("all tags must be strings")
        return v


# ---------------------------------------------------------------
# Validation entry points
# ---------------------------------------------------------------


def validate_explain_response(response: dict) -> ExplainResponse:
    """Validate a /explain response dict against the structural schema and,
    for LLM-generated modes, against the Mode-2 content rules.

    Always enforces:
    - All required fields are present with correct types.
    - engine_signal matches EngineSignalSchema exactly (enum values, list
      element types, required nested fields).

    Additionally enforces for non-SAFE_V1 modes:
    - explanation is non-empty.
    - explanation passes validate_mode_2_negative (no forbidden patterns).

    Raises ExplainSchemaError with a descriptive message on any failure.
    Returns the validated ExplainResponse on success.
    """
    # --- Structural validation (always applied) ---
    try:
        validated = ExplainResponse.model_validate(response)
    except ValidationError as exc:
        raise ExplainSchemaError(f"Structural schema validation failed: {exc}") from exc

    # --- Content validation (only for LLM-generated modes) ---
    if validated.mode != "SAFE_V1":
        if not validated.explanation.strip():
            raise ExplainSchemaError(f"LLM explanation must be non-empty (mode={validated.mode!r})")
        from llm.rag.validators.mode_2_negative import validate_mode_2_negative

        try:
            validate_mode_2_negative(validated.explanation)
        except AssertionError as exc:
            raise ExplainSchemaError(
                f"Explanation failed Mode-2 content validation: {exc}"
            ) from exc

    return validated


def validate_embedded_explain_response(response: dict) -> EmbeddedExplainResponse:
    """Validate the embedded explain_position() response dict.

    Enforces:
    - explanation is present and non-empty.
    - confidence is exactly 'high' or 'low'.
    - tags is a list of strings.

    Raises ExplainSchemaError on failure.
    """
    try:
        return EmbeddedExplainResponse.model_validate(response)
    except ValidationError as exc:
        raise ExplainSchemaError(
            f"Embedded explain response schema validation failed: {exc}"
        ) from exc
