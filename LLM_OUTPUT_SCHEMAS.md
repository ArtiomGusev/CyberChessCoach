Purpose

LLM outputs must follow strict schemas.

This prevents:

hallucinated fields

parsing errors

unstable backend behavior

All LLM responses must be validated before entering the system pipeline.

Coaching Output Schema

Used for move feedback.

{
  "mistake": "string",
  "consequence": "string",
  "better_move": "string",
  "category": "string",
  "severity": "string"
}
Severity values

Allowed values:

blunder
mistake
inaccuracy
acceptable
good
excellent
Category values

Examples include:

tactics
tempo
king_safety
opening_principle
calculation
endgame
strategy
piece_activity
center_control
Recommendation Output Schema

Used when suggesting training.

{
  "training_type": "string",
  "reason": "string",
  "priority": "low | medium | high"
}
Deep Chat Response Schema

Deep chat responses may be less structured but must still include metadata.

Example:

{
  "response": "text",
  "topic": "opening | tactics | strategy | endgame",
  "confidence": 0.0-1.0
}
Output Validation Rules

Before responses are returned:

JSON must parse successfully

required fields must exist

enums must be valid

strings must not be empty

If validation fails:

fallback response must be generated

event logged via SECA Events

LLM Response Constraints

LLM responses must not:

override engine evaluation

invent moves not legal in position

modify player profile

alter system architecture
