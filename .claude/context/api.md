# API Context

## Main Engine Service (`llm/host_app.py`)

- `GET /`
- `GET /health`
- `POST /engine/eval`
- `GET /engine/eval`
- `GET /engine/predictions`
- Debug endpoints under `/debug/*` for redis, book, engine, cache, and miss metrics

This service is engine-first. Preserve limit normalization, cache behavior, and auth gating for debug routes.

## Main Application Service (`llm/server.py`)

Key endpoints include:

- `GET /health`
- `POST /move`
- `POST /live/move`
- `POST /analyze`
- `GET /next-training/{player_id}`
- `POST /game/start`
- `POST /explain`
- `POST /explanation_outcome`

### `/move` Response Contract

`POST /move` returns one of two shapes:

- If the engine pool is unavailable, it returns `{"error": "engine pool unavailable"}`
  with HTTP 200.
- Otherwise it returns the move payload described below.

Do not add, rename, or remove fields without updating Android callers and this
document together.

| Field | Type | Description |
|---|---|---|
| `uci` | string | Best move in UCI notation (e.g. `"e2e4"`). |
| `san` | string | Best move in SAN notation (e.g. `"e4"`). |
| `score` | int | Present only on the heuristic path. Cache, engine, and fallback responses currently omit this field entirely. |
| `source` | string | Where the move came from: `"heuristic"`, `"cache"`, `"engine"`, or `"fallback"`. |
| `opponent_elo` | int | Target ELO used for engine skill limiting (derived from player adaptation). Currently always derived from the `"demo"` player stub, not per-session. |
| `mode` | string | Resolved mode string (e.g. `"blitz"`, `"training"`, `"default"`). |
| `movetime_ms` | int | Resolved movetime in milliseconds after clamping. |
| `nodes` | int | Resolved node budget after clamping. |
| `cache_hit` | bool | `true` if the move was served from `FenMoveCache` without querying the engine. |
| `fallback_used` | bool | `true` only when the move was produced by `fast_fallback_move` after engine selection raised `RuntimeError`. |
| `telemetry` | object | Performance metrics for the request (see below). |

**`telemetry` sub-object:**

| Field | Type | Description |
|---|---|---|
| `latency_ms` | float | Total wall-clock time for the request in milliseconds. |
| `engine_time_ms` | float | Time spent in the engine path in milliseconds. `0.0` on cache hits and heuristic responses. |
| `engine_nodes` | int | Resolved node budget reported to clients. `0` on heuristic responses. Cache hits still report the resolved node budget even though no engine call occurs. |
| `cache_hit_rate` | float | Rolling cache hit rate (0.0-1.0) across recent `/move` requests. |
| `queue_depth` | int | Number of engine workers currently available in the pool. |

**Operational note - silent engine pool startup failure:**
If the engine pool fails to start (e.g. Stockfish binary missing), `server.py`
catches the exception, logs it, and sets `engine_pool = None`. The `/health` endpoint
still returns `{"status": "ok"}`. Any `/move` request while the pool is `None` returns
`{"error": "engine pool unavailable"}` with HTTP 200. Monitoring that relies on
`/health` alone will not detect this degraded state. Use `/debug/engine` (requires
`X-Api-Key`) to check `pool_size`; a value of `0` indicates the pool is absent.

## SECA Routers

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /game/finish`
- `POST /curriculum/next`
- `POST /player/create`
- `POST /player/update/{player_id}`
- `GET /player/state/{player_id}`

## API Rules

- Do not silently drift request or response shapes.
- Keep engine-facing endpoints separate from coaching and player-state responsibilities.
- If an endpoint contract changes, update docs, tests, and any dependent Android or backend callers together.
