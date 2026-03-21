# Deployment Runbook

ChessCoach-AI — production deployment checklist and operational reference.

---

## 1. Required Environment Variables

Set these before starting the server. Missing required variables cause an
explicit `RuntimeError` at startup — the server will not start.

### Server (backend)

| Variable | Required in prod | Default | Description |
|----------|-----------------|---------|-------------|
| `SECA_ENV` | yes | `dev` | Set to `prod`. Enables JWT enforcement and disables debug output. |
| `SECA_API_KEY` | yes | *(none)* | API key for `X-Api-Key` protected routes. Any non-empty string. Server aborts startup if unset when `SECA_ENV=prod`. |
| `SECRET_KEY` | yes | *(random, ephemeral)* | JWT signing secret. Must be ≥ 32 characters. In dev an ephemeral key is generated; all tokens are invalidated on restart. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CORS_ALLOWED_ORIGINS` | yes | *(empty — blocks all cross-origin)* | Comma-separated list of allowed CORS origins (e.g. `https://app.example.com`). Empty value blocks all cross-origin requests and logs a warning. |
| `COACH_OLLAMA_URL` | yes | `http://host.docker.internal:11434` | URL of the running Ollama instance. |
| `COACH_OLLAMA_MODEL` | yes | `qwen2.5:7b-instruct-q2_K` | Ollama model name. Must be pulled before starting. |
| `STOCKFISH_PATH` | no | auto-detected | Override path to Stockfish binary. Auto-detection checks `PATH`, then `/usr/games/stockfish` (Linux) or `engines/stockfish.exe` (Windows). |
| `DATABASE_URL` | no | `sqlite:///data/seca.db` | SQLAlchemy DB URL. Use Postgres in production for multi-worker deployments. |
| `REDIS_URL` | no | *(in-memory only)* | Redis URL for persistent move cache. Omit to use local in-memory cache. |

### Android client (build-time)

| Build config field | Required in release | Default | Description |
|--------------------|--------------------|---------| ------------|
| `COACH_API_BASE` | yes | `http://10.0.2.2:8000` | Base URL of the backend API. Release builds must use `https://`. Set via the `COACH_API_BASE` environment variable at build time (CI secret injection) or in `build.gradle.kts`. |
| `COACH_API_KEY` | yes | *(dev fallback)* | Value sent as `X-Api-Key`. Must match `SECA_API_KEY` on the server. Set via `COACH_API_KEY` env var in CI. |

---

## 2. Startup Assertions

The server performs these checks on startup and fails hard if they are not met:

| Check | Failure mode | Resolution |
|-------|-------------|------------|
| `SECA_API_KEY` set when `SECA_ENV=prod` | `RuntimeError` at import time | Set a non-empty `SECA_API_KEY` |
| Stockfish binary reachable | Engine pool disabled; move endpoints return `{"error": "engine pool unavailable"}` | Install Stockfish or set `STOCKFISH_PATH` |
| Ollama reachable at `COACH_OLLAMA_URL` | Coaching/chat/explain endpoints error at request time | Start Ollama and confirm the model is pulled |
| `CORS_ALLOWED_ORIGINS` non-empty | Warning logged; all cross-origin requests blocked | Set at least one origin |
| DB migration / table creation | Exception at startup | Check `DATABASE_URL` and that the DB is reachable |

Silent failures are not acceptable. Confirm startup log shows no warnings from
any of the checks above before directing traffic to a new instance.

---

## 3. Health Check

```
GET /health
```

**Auth:** none
**Response:** `{"status": "ok"}` with HTTP 200

Use this route for load-balancer health checks and readiness probes.

> **Note:** A 200 response from `/health` confirms the process is alive and
> FastAPI is serving. It does not verify that the engine pool or Ollama are
> functional. For a deeper liveness check, call `GET /debug/engine` (requires
> `X-Api-Key`) and confirm `pool_size > 0`.

---

## 4. Startup Sequence

```bash
# 1. Copy and populate environment
cp .env.example .env
# edit .env: set SECA_ENV=prod, SECA_API_KEY, SECRET_KEY, CORS_ALLOWED_ORIGINS, ...

# 2. Pull the Ollama model (must be done before starting)
ollama pull qwen2.5:7b-instruct-q2_K

# 3. Start the server
python -m uvicorn llm.server:app --host 0.0.0.0 --port 8000 --workers 4
```

Or via Docker Compose:

```bash
docker compose up --build
```

---

## 5. Smoke Tests After Deploy

Run the automated smoke test script (requires `curl` and `python3`):

```bash
# From the repo root on any machine with network access to the server:
./scripts/smoke_test.sh https://api.yourdomain.com "$SECA_API_KEY"

# Or locally against a running dev instance:
./scripts/smoke_test.sh http://localhost:8000 dev-key
```

The script performs three checks and exits non-zero on any failure:

1. `GET /health` → `{"status": "ok"}`
2. `GET /debug/engine` with `X-Api-Key: <key>` → `pool_size > 0`
3. `POST /engine/eval` with the starting FEN → `best_move` is non-null

After confirming the script passes, check the server logs for startup warnings
(CORS, engine pool, DB, Ollama).

---

## 6. CI/CD Secrets and Variables

These must be configured in the GitHub repository before the `deploy` job will
run. Go to **Settings → Secrets and variables → Actions**.

### Secrets (encrypted, never logged)

| Secret name | Where used | How to obtain |
|-------------|------------|---------------|
| `HETZNER_HOST` | SSH deploy step — target address | IP or hostname of your Hetzner VPS |
| `HETZNER_SSH_KEY` | SSH deploy step — private key | Generate with `ssh-keygen -t ed25519`; add the public key to `/home/deploy/.ssh/authorized_keys` on the server (user `deploy`) |
| `COACH_API_KEY` | Android release APK build — baked in as `X-Api-Key` | Any non-empty string; **must match `SECA_API_KEY` in `.env.prod` on the server** |

> `GITHUB_TOKEN` is auto-provisioned by Actions. It is used for GHCR push,
> image attestation, and Trivy scanning. No configuration required.

### Variables (plaintext, visible in logs)

| Variable name | Where used | Example |
|---------------|------------|---------|
| `COACH_API_BASE` | Android release APK build — backend URL | `https://api.yourdomain.com` |

### Server-side environment (Hetzner `/opt/chesscoach/`)

These are not GitHub secrets — they live on the server itself:

| Variable | Required | Description |
|----------|----------|-------------|
| `DOMAIN` | yes | Domain Caddy uses for TLS (e.g. `api.yourdomain.com`) |
| `GHCR_IMAGE` | yes | Full GHCR reference for the api container (e.g. `ghcr.io/owner/cyberchesscoach-llm-api:latest`); referenced by `docker-compose.prod.yml` |

All other backend variables (`SECA_API_KEY`, `SECRET_KEY`, `DATABASE_URL`,
`POSTGRES_*`, etc.) go into `/opt/chesscoach/.env.prod` — see section 1 and
`.env.example` for the full list.

---

## 7. References

- `.env.example` — full variable reference with comments
- `docs/OPERATIONS.md` — runtime monitoring, telemetry, incident response
- `docs/ARCHITECTURE.md` — system design and layer boundaries
- `docs/API_CONTRACTS.md` — authoritative endpoint schemas
