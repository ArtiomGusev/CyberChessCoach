# API Contracts

Authoritative schema contracts for the Chess Coach backend API.
Derived from the production implementation; any deviation constitutes a
**contract mismatch** and must be caught by `test_api_contract_validation.py`.

---

## Conventions

- All endpoints use `Content-Type: application/json`.
- Auth-required endpoints expect `X-Api-Key: <key>` (server.py routes) or
  `Authorization: Bearer <token>` (SECA routes).
- `null` values are allowed for optional fields unless stated otherwise.
- `_metrics` is an internal diagnostic field; clients MUST NOT treat it as
  part of the stable contract (its shape varies by cache source).

---

## 1. `POST /engine/eval`  /  `GET /engine/eval`

**Host:** `host_app.py`
**Auth:** none

### Request (POST body or GET query params)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fen` | `string \| null` | no | FEN string or `"startpos"` |
| `moves` | `string[]` | no | UCI move list (alternative to FEN) |
| `movetime_ms` | `int \| null` | no | Alias: `movetime`. Max engine think time (ms) |
| `nodes` | `int \| null` | no | Max engine nodes to search |

### Response

```json
{
  "score":     <int | null>,
  "best_move": <string | null>,
  "source":    <"engine" | "cache" | "book">,
  "_metrics":  <object>
}
```

| Field | Type | Notes |
|-------|------|-------|
| `score` | `int \| null` | Centipawns from White's perspective. Positive = White better. `null` when engine unavailable (fallback path). |
| `best_move` | `string \| null` | Best move in UCI notation (e.g. `"e2e4"`). `null` when no legal moves or engine unavailable. |
| `source` | `string` | One of `"engine"`, `"cache"`, `"book"`. |
| `_metrics` | `object` | Internal diagnostics. Always present. Structure varies by source. |

### Known mismatches / gaps
- `_metrics` has no stable schema contract; shape depends on `source`.
- `score` semantics (centipawns from White) are not enforced by schema validation.

---

## 2. `GET /next-training/{player_id}`

**Host:** `server.py`
**Auth:** `X-Api-Key` required

### Path params

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | `string` | Player identifier |

### Response

```json
{
  "topic":         <string>,
  "difficulty":    <float>,
  "format":        <string>,
  "expected_gain": <float>
}
```

| Field | Type | Notes |
|-------|------|-------|
| `topic` | `string` | Training topic (e.g. `"tactics"`, `"general_play"`) |
| `difficulty` | `float` | 0.0–1.0 |
| `format` | `string` | Training format (e.g. `"game"`, `"puzzle"`) |
| `expected_gain` | `float` | Estimated rating gain |

### ⚠ Schema conflict with `POST /curriculum/next`

`POST /curriculum/next` is a distinct endpoint (SECA router) with a **different
response schema**:

```json
{
  "topic":         <string>,
  "difficulty":    <float | string>,
  "exercise_type": <string>,
  "payload":       <object>
}
```

The fields `format` / `exercise_type` and `expected_gain` / `payload` are not
interchangeable. Clients MUST NOT assume the two endpoints return the same shape.

---

## 3. `POST /game/finish`

**Host:** `llm/seca/events/router.py`
**Auth:** `Authorization: Bearer <token>` required
**Route prefix:** `/game`

### Request body

```json
{
  "pgn":        <string>,
  "result":     <"win" | "loss" | "draw">,
  "accuracy":   <float 0..1>,
  "weaknesses": <object: {string: float}>,
  "player_id":  <string | null>
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `pgn` | `string` | Non-empty, ≤ 100 000 chars |
| `result` | `string` | Exactly one of `"win"`, `"loss"`, `"draw"` |
| `accuracy` | `float` | 0.0 ≤ value ≤ 1.0 |
| `weaknesses` | `object` | ≤ 50 keys; values are numeric |
| `player_id` | `string \| null` | If provided, must match authenticated player |

### Response

```json
{
  "status":     "stored",
  "new_rating": <float>,
  "confidence": <float>,
  "learning":   <object>,
  "coach_action": {
    "type":     <string>,
    "weakness": <string | null>,
    "reason":   <string>
  },
  "coach_content": {
    "title":       <string>,
    "description": <string>,
    "payload":     <object>
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `status` | `string` | Always `"stored"` on success |
| `new_rating` | `float` | Updated player rating |
| `confidence` | `float` | Updated player confidence |
| `learning` | `object` | Contains `{"status": <string>}` |
| `coach_action.type` | `string` | One of: `"NONE"`, `"REFLECT"`, `"DRILL"`, `"PUZZLE"`, `"PLAN_UPDATE"` |
| `coach_action.weakness` | `string \| null` | Weakness name when type is `DRILL` or `PLAN_UPDATE` |
| `coach_action.reason` | `string` | Human-readable decision reason |
| `coach_content.title` | `string` | Content title shown to player |
| `coach_content.description` | `string` | Content description |
| `coach_content.payload` | `object` | Type-specific content payload |

### ⚠ Executor handler gap (contract mismatch)

`CoachExecutor` has **no handlers** for `PUZZLE` or `PLAN_UPDATE` action types
(only `drill`, `reflect`, `rest` have dedicated handlers; `puzzle_set` is
unreachable because the controller never emits `"PUZZLE_SET"`).

Consequence: when `coach_action.type` is `"PUZZLE"` or `"PLAN_UPDATE"`, the
`coach_content` silently falls back to the default `"Keep playing"` content.
The response is **internally inconsistent**: `coach_action.type` indicates a
specific training recommendation but `coach_content` gives generic text.

This mismatch is captured by `TestCoachExecutorHandlerGap` in
`test_api_contract_validation.py`.

---

## 4. `/coach` — NOT IMPLEMENTED

The `/coach` endpoint does not exist. Coaching decisions are embedded in
the `POST /game/finish` response (`coach_action` + `coach_content` fields).

Any client expecting a standalone `/coach` endpoint will receive HTTP 404.

---

## Error responses

All endpoints return standard FastAPI error shapes:

```json
{ "detail": <string | object> }
```

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Validation error (bad input) |
| 401 | Missing or invalid auth |
| 403 | Authenticated but insufficient permission |
| 413 | Request body exceeds 512 KB |
| 422 | Pydantic validation failure |
| 429 | Rate limit exceeded |
