# Local Development Environments

This is the reference for every way to run the app locally. All modes are
driven by `make` targets, and each mode has a committed env-file template so a
fresh clone works without guesswork.

## Mode matrix

| Mode | Command | Env file | DB | LLM / embeddings | Ports (FE / API) |
|------|---------|----------|----|------------------|------------------|
| **Fully local** | `make docker-up` | `.env.local` (auto-created from template) | Local Postgres (in stack) | Ollama (in stack) | 3000 / 8000 |
| **Fully local, GPU** | `make docker-up-gpu` | `.env.local` | Local Postgres | Ollama + NVIDIA GPU | 3000 / 8000 |
| **Side-by-side dev** | `make docker-up-dev` | `.env.dev` (auto-created from template) | Local Postgres (separate volume) | Ollama (shared model volume) | 3001 / 8001 |
| **Local → prod DB + LLMs** | `make docker-up-local-prod` | `.env.production` (copy template, fill secrets) | **PROD Azure PostgreSQL** | OpenRouter + Azure OpenAI | 3000 / 8000 |
| **ACR backend + local frontend** | `make docker-up-local-prod-acr-be` | `.env.production` | **PROD Azure PostgreSQL** | OpenRouter + Azure OpenAI | 3000 / 8000 |

Env-file templates: `.env.local.example`, `.env.dev.example`,
`.env.production.example` (repo root). `.env.local` and `.env.dev` are created
automatically on first `make docker-up` / `make docker-up-dev`;
`.env.production` must be created by hand because it holds real secrets.

## 1. Fully local (`make docker-up`)

Everything on your machine: FastAPI + Next.js + Postgres/pgvector + Ollama.
No secrets or cloud accounts needed.

```bash
make docker-up          # CPU
make docker-up-gpu      # NVIDIA GPU for Ollama
docker compose logs -f  # watch startup
make docker-down        # stop
```

First-run behavior:

- Ollama pulls its models (`mistral:7b`, `mxbai-embed-large`) — 5–10 min.
- The `db-init` one-shot container loads the KJV Bible and generates
  embeddings automatically (`docker compose logs -f db-init` to follow).
  It exits and skips itself on subsequent starts.

Endpoints: frontend <http://localhost:3000>, API <http://localhost:8000>
(docs at `/docs`, liveness at `/health/live`).

To use OpenRouter for chat while keeping local embeddings, uncomment the
OpenRouter block in `.env.local` and set your key.

### Ollama requirements

Ollama runs as a container inside the stack — no host install needed. What it
does need:

- **Disk**: ~5GB for the default models — `mistral:7b` (~4.4GB, chat) and
  `mxbai-embed-large` (~670MB, embeddings). `scripts/init-ollama.sh` pulls
  them automatically on container start; nothing to do manually. When
  `LLM_PROVIDER=openrouter`, the chat model is deliberately *not* pulled —
  only the embedding model.
- **RAM/GPU**: `mistral:7b` on CPU wants ~8GB free RAM; with an NVIDIA GPU
  (8GB+ VRAM) use `make docker-up-gpu` / `make docker-up-dev-gpu` (requires
  the NVIDIA Container Toolkit on the host).
- **Model cache volume**: models live in a Docker volume with the fixed name
  `ollama_data`, shared between the main stack and the dev stack so they are
  downloaded once. The dev stack declares it `external` (so `docker compose
  down -v` can never delete it); `make docker-up-dev` creates it when
  missing. If you bypass make: `docker volume create ollama_data`.

**Upgrading from an older checkout:** the main stack previously stored models
in a project-prefixed volume (`getinspiredbythebible_ollama_data`). After
pulling this change, either let Ollama re-download the models once, or copy
the old cache into the shared volume:

```bash
docker volume create ollama_data
docker run --rm \
  -v getinspiredbythebible_ollama_data:/from -v ollama_data:/to \
  alpine sh -c "cp -a /from/. /to/"
```

## 2. Side-by-side dev stack (`make docker-up-dev`)

A second, fully isolated stack (`-p getinspired-dev`) for machines that
already run the main stack (e.g. a self-hosted prod box). Ports are shifted:
frontend 3001, API 8001, Postgres 5433, Ollama 11435.

```bash
make docker-up-dev        # CPU
make docker-up-dev-gpu    # NVIDIA GPU (adds docker-compose.gpu.yml overlay)
make docker-logs-dev
make docker-down-dev
```

Notes:

- The Ollama **model** volume (`ollama_data`) is shared with the main stack to
  avoid re-downloading models (see "Ollama requirements" above);
  `make docker-up-dev` creates the volume if it doesn't exist yet, so this
  also works on a fresh machine (first start then downloads models into it).
- The Postgres volume (`postgres_data_dev`) is separate — embeddings and data
  never mix with the main stack.
- Database init: `make docker-reinit-dev-db`, logs via `make docker-logs-dev-init`.

## 3. Local against PROD DB + prod LLMs (`make docker-up-local-prod`)

Runs the API and frontend locally (with hot reload) but wired to the **real
production database** (Azure PostgreSQL) and the production LLM providers
(OpenRouter for chat, Azure OpenAI for embeddings). No Ollama, no local
Postgres — fast startup, real data.

> ⚠️ **You are touching production data.** Anything the app writes (feedback,
> usage tracking, blocked-sample capture) lands in the prod DB.

Setup (once):

```bash
cp .env.production.example .env.production
# Fill in: DATABASE_URL, OPENROUTER_API_KEY, AZURE_OPENAI_ENDPOINT/API_KEY
make az-pg-add-ip        # allow your current IP on the Azure PG firewall
```

Run:

```bash
make docker-up-local-prod          # cached images (fast)
make docker-up-local-prod-build    # rebuild images from source
make docker-logs-local-prod        # tail logs
make docker-restart-local-prod-api # restart API only
make docker-down-local-prod        # stop
```

### Variant: production backend image from ACR

Same wiring, but the API runs the exact image deployed to production
(`bible-backend` from ACR) instead of building from your working tree. Useful
to reproduce prod behavior locally.

```bash
az acr login --name bibleappacrmb0172     # or $ACR_NAME from .env.production
make docker-up-local-prod-acr-be              # :latest
make docker-up-local-prod-acr-be TAG=abc1234  # specific git-SHA tag (see make az-acr-list-tags)
```

## 4. Without Docker (bare processes)

```bash
make setup-dev                     # venv + deps + pre-commit hooks
source .venv/bin/activate

# API (set DATABASE_URL to a running Postgres, e.g. the docker one on :5432)
cd api && uvicorn main:app --reload

# Frontend
cd frontend && npm run dev
```

## Troubleshooting

- **`env file .env.local not found`** — run `make docker-up` (it creates the
  file from the template) or `cp .env.local.example .env.local`.
- **API up but DB errors in local mode** — `DATABASE_URL` in your env file
  overrides the compose default; for the local stack it must point at
  `postgres:5432` (the service name), not `localhost`.
- **`connection refused` / timeout against the prod DB** — your IP is not on
  the Azure PG firewall: `make az-pg-add-ip` (list rules with
  `make az-pg-list-rules`).
- **`unauthorized` pulling the ACR image** — `az acr login --name <ACR_NAME>`.
- **Dev stack: `could not select device driver "nvidia"`** — you used the GPU
  target on a machine without the NVIDIA container toolkit; use
  `make docker-up-dev` (CPU) instead.
- **`external volume "ollama_data" not found`** — you ran docker compose
  directly instead of via make; run `docker volume create ollama_data` once
  (or `make docker-up-dev`, which does it for you).
- **Health checks** — liveness `GET /health/live`, readiness
  `GET /health/ready`, full diagnostics `GET /health` (localhost only).
- **Sanity checks** — `make functional-test` (main stack) or
  `make functional-test-dev` (dev stack).
