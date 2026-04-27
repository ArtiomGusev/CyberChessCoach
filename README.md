# ChessCoach-AI

A non-calculating chess coach. Stockfish is the source of truth; the LLM explains the engine's evaluation in natural language but never overrides it, never suggests moves, and never invents tactics.

The system has three layers:

1. **Engine** — Stockfish provides evaluations and best-move analysis. The raw output is normalised through an Engine Signal Vector (ESV) before any other layer sees it.
2. **Mode-2 explainer** — a deterministic RAG retrieval, prompt rendering, and LLM generation pipeline that turns the ESV into prose. Every output passes through hard validators that reject move suggestions, invented tactics, or any deviation from the engine's truth.
3. **SECA** — a thin per-user adaptation layer (rating, confidence, embeddings, deterministic action selection). The base intelligence (engine, LLM) stays fixed; only lightweight decision-layer state updates per game. Autonomous RL is prohibited by design.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the invariants the system is built to guarantee, and [`docs/SECA.md`](docs/SECA.md) for what is live vs. deferred in the adaptation loop.

## Repository layout

| Directory | Contents |
|---|---|
| [`llm/`](llm/) | Python FastAPI backend: API routes, RAG, validators, auth, SECA flows, engine pool |
| [`android/`](android/) | Kotlin Android client (Atrium UI) + JNI engine bridge |
| [`engine/`](engine/) | Native chess engine experiments (perft, strength) |
| [`docs/`](docs/) | Architecture, testing, operations, deployment, release |
| [`design/`](design/) | React/Babel design-canvas mockups (visual prototype only) |
| [`scripts/`](scripts/) | Setup, deploy, smoke-test, and Android emulator scripts |

## Quick start

For full setup options (Docker, dev container, bare-metal, Android) see the **Developer Setup** section of [`CLAUDE.md`](CLAUDE.md).

The shortest path to a running backend:

```bash
cp .env.example .env

# Ollama runs on the host, not in Docker
ollama pull qwen2.5:7b-instruct-q2_K
ollama serve &

docker compose up
```

The API is then reachable at `http://localhost:8000`:

```bash
curl http://localhost:8000/health
```

For the Android app, open [`android/`](android/) in Android Studio — it generates `local.properties` automatically — and run on an emulator or `arm64-v8a` device.

## Tests

Backend (Python):

```bash
python llm/run_ci_suite.py          # CI suite
python llm/run_quality_gate.py      # black + pylint + mypy
```

Android (host JVM unit tests):

```bash
cd android && ./gradlew test
```

Android instrumented (emulator or device):

```bash
bash scripts/run_connected_android_tests.sh
```

CI runs a subset of these on every push; see [`docs/TESTING.md`](docs/TESTING.md) for the full policy on which tests gate merges and which (real-LLM regression, quality heuristics) run only locally.

## Deployment

Production runs on Hetzner via Docker Compose + Caddy + Ollama. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the bootstrap script, secrets list, and post-deploy smoke test; [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for runtime monitoring and incident response.

## Documentation

| Document | Purpose |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System invariants and layer boundaries |
| [`docs/SECA.md`](docs/SECA.md) | Adaptive layer: framework, six-step loop, live-vs-dormant map |
| [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md) | Authoritative HTTP request/response schemas |
| [`docs/TESTING.md`](docs/TESTING.md) | Test taxonomy, CI policy, regression frequency |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Production deployment runbook |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Telemetry, regression detection, incident response |
| [`docs/OPERATIONS_RETRIES.md`](docs/OPERATIONS_RETRIES.md) | Retry policy reference |
| [`docs/RELEASE.md`](docs/RELEASE.md) | Release process |
| [`CLAUDE.md`](CLAUDE.md) | Project rules, required reviews, subagent routing, developer setup |

## Design canvas

The React/Babel mockups under [`design/`](design/) (loaded by [`design/index.html`](design/index.html)) are a visual prototype of the Cereveon · Atrium design language for the Android client. They are not part of the build — open `design/index.html` in a browser to view them. The Android implementation lives in `android/app/src/main/`.

## License

See [`LICENSE.md`](LICENSE.md).
