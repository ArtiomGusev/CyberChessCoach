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
