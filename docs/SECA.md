# SECA — Skill-Estimating Coaching Architecture

The `llm/seca/` tree is the chess-coach backend's largest subsystem.
It owns auth, the per-player game lifecycle, opening repertoire,
skill tracking, the post-game coach pipeline, and the dormant
adaptive-learning research code that's intentionally frozen at
runtime.

> The name was originally meant to evoke "Self-Evolving Coaching
> Architecture" — the open-ended adaptive system the early commits
> aspired to.  The runtime today is the disciplined subset of that
> idea: deterministic skill estimation + scripted coaching, with the
> evolutionary half explicitly fenced off.

---

## What lives in the live runtime

These layers are loaded by every authenticated request and are
under the test suite + the freeze guard's keyword scan.

| Layer | Module | Responsibility |
|-------|--------|----------------|
| **auth** | `seca/auth/` | Register / login / sessions / JWT issuance + sliding refresh.  Token lifecycle (incl. the `X-Auth-Token` rotation header).  PBKDF2 password hashing + email-enumeration timing defence. |
| **events** | `seca/events/` | `POST /game/finish` — stores GameEvent, runs SkillUpdater, dispatches to PostGameCoach. |
| **storage** | `seca/storage/` | Raw-sqlite tables for `games`, `moves`, `explanations`, `repertoire`.  Boundary partner of the SQLAlchemy auth schema (see `test_schema_boundary.py`). |
| **skills** | `seca/skills/` | `SkillUpdater` — translates a finished `GameEvent` into rating / confidence / skill-vector deltas. |
| **adaptation** | `seca/adaptation/` | Per-session ELO drift for skill-assessment games.  No neural updates, no bandit training — fixed quality-delta table, in-memory state per player. |
| **coach** | `seca/coach/` (live) | `PostGameCoachController` + `CoachExecutor` — chooses + renders the post-game coaching action returned in `/game/finish`. |
| **analytics** | `seca/analytics/` | `AnalyticsLogger` (event log) + training recommendations derived from accumulated weakness counts. |
| **analysis** | `seca/analysis/` | `HistoricalAnalysisPipeline` — deterministic per-player roll-up over recent games (dominant weakness category, etc.).  Read-only. |
| **api** | `seca/api/` | Routers + key middleware.  X-API-Key enforcement (`auth/api_key.py`), shared rate limiter. |
| **safety** | `seca/safety/` | The freeze guard described below — the single runtime enforcement of the "no autonomous RL" rule. |
| **runtime** | `seca/runtime/` | `safe_mode.py` — `SAFE_MODE = True` constant + `assert_safe()` import-time gate that any forbidden module would trip. |

---

## The algorithm idea (and why most of it is frozen)

The earliest SECA commits sketched a **closed-loop adaptive coach**:

```
        ┌────────────────────────────────────────┐
        │              World Model               │
        │  (skill dynamics: skill_t → skill_t+1) │
        └──────────────┬─────────────────────────┘
                       │ predict(skill, action)
                       ▼
        ┌────────────────────────────────────────┐
        │           Counterfactual Planner       │
        │   argmax_a  reward(world_model.predict(│
        │              skill, a))                │
        └──────────────┬─────────────────────────┘
                       │ chosen training action
                       ▼
        ┌────────────────────────────────────────┐
        │       Contextual Bandit (online)       │
        │   ε-greedy over arms (tactics / opening│
        │   / endgame / etc.); reward = ΔELO     │
        └──────────────┬─────────────────────────┘
                       │ logged context+action+reward
                       ▼
        ┌────────────────────────────────────────┐
        │      Online learning (ΔELO → fit)      │
        │   skill embedding update,              │
        │   bandit weights update,               │
        │   world-model regression refit         │
        └──────────────┬─────────────────────────┘
                       │ next session uses fresh weights
                       ▲
                       │
        ┌──────────────┴─────────────────────────┐
        │            User plays a game           │
        │   GameEvent → reward signal → loop     │
        └────────────────────────────────────────┘
```

Concretely: `seca/world_model/model.py` is a 2-layer MLP
(`SkillDynamicsModel`) that predicts `skill_t+1` from `(skill, action)`;
`seca/brain/bandit/contextual_bandit.py` is a bandit head that picks
training arms; a `CounterfactualPlanner` (referenced from inside the
unreachable `if not SAFE_MODE:` branch in `events/router.py`) was
the plan-to-evaluate stage; `seca/learning/online_learner.py` is the
gradient step that would have closed the loop.

**None of that runs today.**  Per `CLAUDE.md` rule #3 ("Autonomous RL
implementation is prohibited") and `docs/ARCHITECTURE.md` "Forbidden
Changes", the project decided the adaptive-learning surface was too
broad to ship correctness guarantees against.  The research code
remains in the tree for future study but cannot be loaded into the
live runtime.

What ships instead is the **deterministic backbone** of that loop:
`SkillUpdater` does the bookkeeping side (rating + confidence + skill
vector after each game) without any neural component, and the
post-game coach picks an action from a small fixed set rather than
from a learned policy.  Closed-loop learning is replaced with
**human-in-the-loop calibration**: the user re-tunes their estimate
via the Settings → Skill rating affordance, and the server stores it
verbatim through `PATCH /auth/me`.

---

## The freeze guard

`seca/safety/freeze.py` is the single runtime-enforcement layer for
the "no autonomous RL" rule.  Called once at FastAPI startup; calls
`sys.exit(1)` immediately if any forbidden component has been loaded.

Three independent checks (defence in depth):

1. **Brain-tree allowlist.**  Anything under `llm.seca.brain.*` that
   isn't on the explicit allowlist is forbidden — regardless of name
   or contents.  The allowlist is intentionally tiny (only the
   SQLAlchemy schema modules + two helpers needed by the live skill
   updater).  *New* brain modules cannot be silently loaded by
   appearing in `sys.modules`; they must be deliberately added here.

2. **Forbidden module-name parts.**  Substring matches against module
   names used by historical or hypothetical adaptive components
   elsewhere in the tree.  Fallback for code paths that may move
   outside `brain/` in future refactors.

3. **Forbidden source keywords.**  Substring matches against module
   *source text* — covers the major training entry points used by
   the dormant ML code (`optimizer.step`, `loss.backward`,
   `.partial_fit(`, `train(`, `bandit.update`, etc.).

Plus two defensive guards:

- `assert_safe_world_model(world_model)` — only the `SafeWorldModel`
  stub class (a no-op `predict_next` that returns the input state
  unchanged) is allowed to be the live world model.
- `assert_no_background_tasks()` — the env var
  `SECA_ENABLE_ONLINE_LEARNING=1` is treated as a deliberate attempt
  to bypass the freeze and crashes the process.

The tests in `test_safety_freeze.py` (16 cases) pin every check
against intentional violations.

---

## Where the SECA layers wire into the API

| Endpoint | SECA layer(s) it touches |
|----------|--------------------------|
| `POST /auth/{register,login,logout}` | `auth/router.py`, `auth/service.py`, `auth/tokens.py` |
| `GET /auth/me` / `PATCH /auth/me` | `auth/router.py`; PATCH writes back into `auth/models.Player` |
| `POST /game/start` | `storage/repo.create_game` |
| `POST /game/finish` | `events/router.py` → `events/storage.EventStorage` (game event row) → `skills/updater.SkillUpdater` (rating delta) → `coach/postgame_controller` (coach action) → `analytics/training_recommendations` |
| `POST /game/{id}/checkpoint` | `storage/repo.checkpoint_game` |
| `GET /game/active` | `storage/repo.get_active_game` |
| `GET /game/history` | `events/storage.EventStorage.get_recent_games` |
| `GET /repertoire` | `storage/repo.list_repertoire` (+ default fallback in `server.py`) |
| `POST /chat`, `POST /chat/stream` | upstream of SECA — handled by the LLM coach layer in `server.py` (Mode-2 explainer; see `docs/ARCHITECTURE.md`) |

Authenticated endpoints depend on `seca/auth/router.get_current_player`,
which both validates the session AND attaches the `X-Auth-Token`
refresh header.  Sliding-session expiry extension lives in
`seca/auth/service.AuthService.get_player_by_session`.

---

## Why the seca/ tree looks bigger than what runs

A grep across `llm/seca/` reveals directories that aren't in the
"live runtime" table above: `henm/`, `closed_loop/`, `optim/`,
`evolution/`, `policy/`, `world_model/`, `world/`, `memory/`,
`coaching/`, etc.  These are the **dormant research code paths**
preserved for future study.  They:

- Cannot be imported into a live process (the freeze guard would
  crash startup if they were).
- Are excluded from the active code paths the test suite exercises.
- Should never be referenced from anything under `seca/api/`,
  `seca/auth/`, `seca/events/`, `seca/skills/`, `seca/adaptation/`,
  `seca/coach/`, `seca/analytics/`, `seca/analysis/`, or
  `seca/storage/`.

If a contributor needs to revive any of that code, the path is:
move the relevant module *out* of the freeze-guard's blast radius
(rename, split, etc.), add it to the brain allowlist if applicable,
update `docs/ARCHITECTURE.md` "Forbidden Changes", and write tests
that pin its determinism guarantees.  No silent re-enablement.

---

## References

- `CLAUDE.md` — rule #3 (Autonomous RL implementation is prohibited)
- `docs/ARCHITECTURE.md` — Forbidden Changes; engine + Mode-2 layer
- `docs/API_CONTRACTS.md` — endpoint schemas
- `llm/seca/safety/freeze.py` — the enforcement layer
- `test_safety_freeze.py` — invariants pinned against violations
