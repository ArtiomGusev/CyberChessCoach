# SECA — Self-Evolving Coaching Architecture (v1)

SECA is the framework underneath `llm/seca/` — a feedback loop that
adapts to individual users without retraining the underlying neural
networks.  This doc describes what SECA v1 *is*, walks the canonical
six-step loop, and pins the loop's live-vs-dormant status in this
implementation against the framework's reference description.

For HTTP schemas see [`API_CONTRACTS.md`](API_CONTRACTS.md); for the
LLM Mode-2 explainer (downstream of SECA) see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## The framework in one paragraph

SECA defines a third path between static AI (strong but
non-adaptive) and self-improving AI (powerful but unstable).  The
underlying intelligence — chess engine, language model, recommender
— stays fixed.  Adaptation lives in a thin **decision layer**:
contextual bandits, lightweight embeddings, deterministic skill
trackers.  Every interaction observes a state, selects an action,
records a reward, and updates the decision-layer components in
real time.  No gradient descent over large models, no
self-modifying weights, no uncontrolled feedback loops.

The result is a system that adapts immediately, costs almost
nothing in compute, and is interpretable end-to-end: every action
choice can be traced to a state + a reward history.

---

## The v1 algorithm — six-step loop

```
                ┌───────────────────────────────┐
                │ 1. Input                      │
                │   state + user profile        │
                │   (rating, confidence,        │
                │    embedding)                 │
                └──────────────┬────────────────┘
                               ▼
                ┌───────────────────────────────┐
                │ 2. Action selection           │
                │   contextual bandit           │
                │   argmax_a Q(state, profile, a)│
                └──────────────┬────────────────┘
                               ▼
                ┌───────────────────────────────┐
                │ 3. Output                     │
                │   action + context →          │
                │   user-facing response        │
                └──────────────┬────────────────┘
                               ▼
                ┌───────────────────────────────┐
                │ 4. Feedback signal            │
                │   numerical reward            │
                │   (outcome / engagement /     │
                │    error rate)                │
                └──────────────┬────────────────┘
                               ▼
                ┌───────────────────────────────┐
                │ 5. Online update              │
                │   bandit incorporates         │
                │   (state, action, reward);    │
                │   profile (rating, conf,      │
                │   embedding) refreshed.       │
                │   No retraining, no gradient  │
                │   descent over base model.    │
                └──────────────┬────────────────┘
                               ▼
                ┌───────────────────────────────┐
                │ 6. Loop repeats               │
                │   next interaction            │
                └───────────────────────────────┘
```

The constraint that makes the loop tractable: **base intelligence is
held fixed**.  In this codebase that's Stockfish (engine) and the
LLM (Mode-2 explainer).  Adaptation never touches their weights.

---

## What's live in this implementation

The chess coach implements parts of the loop today and intentionally
defers others.  Mapping each step against the canonical algorithm:

| Step | What v1 prescribes | What this codebase ships |
|------|-------------------|--------------------------|
| **1. Input** | State + user profile (rating, confidence, embedding) | **Live.**  `seca/auth/models.Player` carries `rating`, `confidence`, `skill_vector_json`, `player_embedding`.  `seca/brain/bandit/context_builder.build_context_vector()` assembles a 6-element feature vector from rating + confidence + accuracy + weaknesses. |
| **2. Action selection** | Contextual bandit over a domain action space | **Deferred.**  Live runtime uses a *deterministic* `PostGameCoachController` (rule-based action selection from a small fixed action set), not a bandit.  Per CLAUDE.md rule #3 the project chose to ship the bandit-driven decision step only after the deterministic baseline is well understood; the bandit code under `seca/brain/bandit/contextual_bandit.py` exists but is dormant. |
| **3. Output** | Action + context → user-facing response | **Live.**  `seca/coach/executor.CoachExecutor` renders the chosen action into a `coach_content` payload returned by `/game/finish`. |
| **4. Feedback signal** | Numerical reward from the interaction | **Live.**  Per-game `accuracy`, `weaknesses`, and the rating delta from `SkillUpdater` together form the reward signal logged to `bandit_experiences`. |
| **5. Online update** | Bandit + auxiliary refresh; no retraining | **Live (auxiliary side).**  `seca/skills/updater.SkillUpdater` refreshes rating, confidence, skill vector, and player embedding (`PlayerEmbeddingEncoder`) per game.  `seca/brain/bandit/experience_store.ExperienceStore` writes the (context, action, reward) tuple for the bandit.  **Bandit weight update itself: dormant** — the live system logs experiences but doesn't fit a policy from them. |
| **6. Loop repeats** | Next interaction picks up the refreshed profile | **Live.**  Subsequent `/game/finish` calls read the updated player row; `/auth/me` returns the current state to the client. |

In short: this codebase ships the **half of the loop that doesn't
need a learned policy** (state assembly, deterministic action,
output rendering, reward extraction, lightweight profile refresh,
experience logging) and defers the **bandit-as-decision-maker**
half.  The framework calls this "SECA v1 with deferred decision
layer" — a valid configuration, since the framework's invariants
hold either way.

There is one further self-imposed constraint specific to this
project: **no continuous-feedback retraining of any neural model**,
period.  The framework permits lightweight online updates (bandit
weights, embeddings); this implementation goes further and requires
that the embedding refresh be deterministic too (no gradient steps
in the live runtime, ever).  See "Freeze guard" below.

---

## Live runtime layers

The directories under `llm/seca/` that participate in the live
request path:

| Layer | Module | Responsibility |
|-------|--------|----------------|
| **auth** | `seca/auth/` | Register / login / sessions / JWT issuance + sliding refresh.  Token lifecycle (incl. the `X-Auth-Token` rotation header). |
| **events** | `seca/events/` | `POST /game/finish` — stores GameEvent, runs SkillUpdater, dispatches to PostGameCoach. |
| **storage** | `seca/storage/` | Raw-sqlite tables for `games`, `moves`, `explanations`, `repertoire`. |
| **skills** | `seca/skills/` | `SkillUpdater` — translates a finished GameEvent into rating / confidence / skill-vector / embedding deltas (step 5 of the loop, auxiliary side). |
| **adaptation** | `seca/adaptation/` | Per-session ELO drift for skill-assessment games — fixed quality-delta table, in-memory state per player.  Deterministic. |
| **coach** | `seca/coach/` | `PostGameCoachController` (live action selection — currently rule-based, not bandit-driven) + `CoachExecutor` (renders the action). |
| **analytics** | `seca/analytics/` | `AnalyticsLogger` (event log) + training recommendations derived from accumulated weakness counts. |
| **analysis** | `seca/analysis/` | `HistoricalAnalysisPipeline` — deterministic per-player roll-up over recent games.  Read-only. |
| **brain** (allowlisted only) | `seca/brain/bandit/{context_builder,experience_store}` | The two helpers participate in the loop today.  Everything else under `brain/` is dormant. |
| **learning** (allowlisted only) | `seca/learning/player_embedding` | Embedding encoder + JSON serialisation, used by SkillUpdater. |
| **api** | `seca/api/` | Routers + middleware (X-API-Key, shared rate limiter). |
| **safety** | `seca/safety/` | Freeze guard — single runtime enforcement of the no-retraining rule. |
| **runtime** | `seca/runtime/` | `safe_mode.py` — `SAFE_MODE = True` constant + `assert_safe()` import-time gate. |

---

## What's dormant and why

Several `seca/` directories are *not* in the live path: `world_model/`,
`world/`, `henm/`, `closed_loop/`, `optim/`, `evolution/`, `policy/`,
`memory/`, plus most of `brain/` (everything not in the allowlist).
These hold research code for the **deferred decision layer** + the
**not-permitted-in-v1 self-improving variants** beyond the framework's
constraints:

- `seca/world_model/model.SkillDynamicsModel` — a 2-layer MLP that
  predicts `skill_t+1` from `(skill, action)`.  Would be the dynamics
  model for a counterfactual planner.
- `seca/brain/bandit/contextual_bandit` — the bandit decision step
  (step 2 in the loop above), dormant pending the deterministic
  baseline being well understood.
- `seca/brain/bandit/online_update`, `seca/learning/online_learner` —
  the gradient steps that would refit the bandit / embedding
  encoder online.  These are what the framework's "no gradient
  descent over large models" rule explicitly excludes.
- `seca/closed_loop/`, `seca/evolution/`, `seca/optim/` — beyond
  v1's constraints (these explore self-improving variants the
  framework's v1 spec rules out by design).

If a contributor needs to revive any of this for the bandit-decision
step (the framework-permitted next milestone), the path is: move
the relevant module out of the freeze guard's blast radius, add
the new live module to the brain allowlist, document its
determinism guarantees, and write tests that pin them.  No silent
re-enablement.

---

## Freeze guard

`seca/safety/freeze.py` enforces the no-retraining rule at startup.
Three independent checks:

1. **Brain-tree allowlist.**  Anything under `llm.seca.brain.*` not
   on the allowlist is forbidden.  Allowlist is intentionally tiny:
   schema modules + the two helpers (`context_builder`,
   `experience_store`) the live loop actually uses.
2. **Forbidden module-name parts.**  Substring matches against names
   used by historical adaptive components (e.g. `brain.rl`,
   `brain.bandit.online`).
3. **Forbidden source keywords.**  Substring matches against module
   *source text*: `optimizer.step`, `loss.backward`, `.partial_fit(`,
   `train(`, `bandit.update`, etc.  Catches gradient updates anywhere
   in the seca tree even if a module is renamed around the
   allowlist.

Plus two defensive guards:

- `assert_safe_world_model(world_model)` — only the `SafeWorldModel`
  stub (a no-op `predict_next` that returns the input state
  unchanged) is allowed to be the live world model.
- `assert_no_background_tasks()` — `SECA_ENABLE_ONLINE_LEARNING=1`
  is treated as a deliberate bypass attempt and crashes the process.

`test_safety_freeze.py` (16 cases) pins every check against
intentional violations.

What the guard *doesn't* block: the lightweight updates v1 permits.
`SkillUpdater`'s rating / confidence / embedding refresh runs every
game; the bandit experience store writes every game.  The framework
v1 explicitly distinguishes "incremental decision-layer update"
(allowed) from "gradient descent on a learned model" (not allowed),
and the guard's keyword list is calibrated against the latter.

---

## Where the loop wires into the API

| Endpoint | SECA layer(s) it touches | Loop step |
|----------|--------------------------|-----------|
| `POST /auth/{register,login,logout}` | `auth/router.py`, `auth/service.py`, `auth/tokens.py` | (auth, not the loop) |
| `GET /auth/me` / `PATCH /auth/me` | `auth/router.py`; PATCH writes back into `auth/models.Player` | 1 (state read) / 5 (manual profile refresh) |
| `POST /game/start` | `storage/repo.create_game` | (lifecycle) |
| `POST /game/finish` | `events/router.py` → `events/storage.EventStorage` (game event) → `skills/updater.SkillUpdater` (rating / embedding refresh) → `coach/postgame_controller` (action selection) → `coach/executor` (output rendering) → `analytics/training_recommendations` | 1 → 4 → 5 → 2 → 3, per game |
| `POST /game/{id}/checkpoint` | `storage/repo.checkpoint_game` | (cross-device resume) |
| `GET /game/active` | `storage/repo.get_active_game` | (cross-device resume) |
| `GET /game/history` | `events/storage.EventStorage.get_recent_games` | (read-only history) |
| `GET /repertoire` | `storage/repo.list_repertoire` (+ default fallback in `server.py`) | (study material) |
| `POST /chat`, `POST /chat/stream` | upstream of SECA — handled by the LLM coach layer in `server.py` (Mode-2 explainer; see `ARCHITECTURE.md`) | (Mode-2, not the SECA loop) |

Authenticated endpoints depend on
`seca/auth/router.get_current_player`, which both validates the
session AND attaches the `X-Auth-Token` refresh header.  Sliding
session expiry extension lives in
`seca/auth/service.AuthService.get_player_by_session`.

---

## The framework beyond chess

SECA v1 is domain-agnostic.  The same six-step loop applies to:

- **Adaptive learning platforms** — state = current lesson + student
  profile; action = next exercise; reward = mastery delta.
- **Developer tooling** — state = project + code context; action =
  suggestion / refactor; reward = accept / reject signal.
- **Cognitive training** — state = recent performance + cognitive
  profile; action = next drill; reward = improvement on a held-out
  benchmark.
- **Dynamic difficulty in games** — state = player + recent
  performance; action = enemy parameters / level layout; reward =
  retention / engagement.
- **Productivity / habit formation** — state = recent actions +
  user profile; action = next prompt / nudge; reward = completion
  signal.
- **Health coaching** — state = vitals + history; action =
  workout / nutrition / sleep prescription; reward = adherence +
  progress.

The core invariant — base intelligence stays fixed, adaptation lives
in the decision layer, every action is interpretable — survives
across every domain.

---

## Why v1's constraints are features

SECA v1 deliberately rules out autonomous training, self-modifying
models, and uncontrolled feedback loops.  These are not limitations
to be patched out in v2; they are what makes v1 deployable.  In
return for the constraint, you get:

- **Deployability.**  A v1 system can ship to production today; a
  fully self-improving variant cannot.
- **Auditability.**  Every action choice is a function of a state
  + a logged reward history.  No opaque weight updates entangle
  the explanation.
- **Stability.**  No risk of catastrophic forgetting, weight
  divergence, or regression on previously-handled cases.
- **Cost.**  No retraining infrastructure, no gradient compute, no
  large-model checkpointing.

The framework's bet is that **most "self-improving" capabilities
people actually want are achievable inside the v1 envelope** — the
adaptation users notice is the rapid, real-time, per-interaction
kind, not the slow weight-update-and-redeploy kind.

---

## References

- The framework article: *SECA v1: A Practical Framework for Adaptive Intelligence*
- `CLAUDE.md` — rule #3 (autonomous RL prohibited)
- `docs/ARCHITECTURE.md` — Forbidden Changes; engine + Mode-2 layer
- `docs/API_CONTRACTS.md` — endpoint schemas
- `llm/seca/safety/freeze.py` — the enforcement layer
- `test_safety_freeze.py` — invariants pinned against violations
