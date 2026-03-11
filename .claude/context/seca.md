# SECA Context

## SECA Modules

SECA logic lives under `llm/seca/` and is split across:

- `auth/`: registration, login, logout, token handling, and rate limiting.
- `events/`: game finish ingestion and event storage.
- `coach/` and `coaching/`: post-game and live coaching decisions plus execution.
- `curriculum/`: next-training and lesson selection logic.
- `player/`: player creation, state, updates, and progression history.
- `brain/`, `analytics/`, `storage/`: deterministic models, telemetry, persistence, and internal updates.

## Data and Runtime Assumptions

- Auth uses SQLite at `data/seca.db`.
- Player state, events, and rating or confidence updates are persisted and reused across flows.
- `SAFE_MODE` gates risky or experimental learning paths.
- Learning and planner modules exist, but expanding them into autonomous RL behavior is out of bounds.

## SECA Change Rules

- Preserve auth and player-state contracts.
- Keep deterministic classification and update logic inside SECA layers, not in UI or prompt text.
- Prefer explicit schema updates when request or response shapes change.
- When touching `events/`, `auth/`, `curriculum/`, or `player/`, add or update backend tests.
