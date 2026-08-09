# BITB-092: Fix Dev Stack `db-init` Migration Failure and Embedding Config Drift

**Status:** ✅ Done
**Priority:** P1
**Size:** S
**Created:** 2026-08-09
**Completed:** 2026-08-09

## User Story

**As a** developer running `make docker-up-dev`, **I want** the dev stack's `db-init` service to
successfully run migrations and the API/db-init embedding configuration to match the main local
stack, **so that** local dev testing works out of the box instead of crashing on startup.

## Problem

`docker-compose.dev.yml`'s `db-init` service runs `scripts/migrations/run_migrations.py`, which
resolves its `api/` package two directories up from its own file (`../../api`) — the same layout
`docker-compose.yml`'s (production/main local stack's) `db-init` service exposes via the
`./api:/api:ro` mount. The dev compose file was missing that mount entirely, so `db-init` crashed
with `ModuleNotFoundError: config` before migrations could run, and `/api/config.py` was never
visible inside the container.

Separately, the dev stack's embedding configuration had drifted between services:

- `api` was missing `EMBEDDING_DIMENSIONS`.
- `db-init` was missing `EMBEDDING_PROVIDER` and `EMBEDDING_DIMENSIONS`.

This meant the mxbai-embed-large / 1024-dimension defaults used by the main stack were not
consistently applied across the dev stack's `api` and `db-init` services, risking embedding
dimension mismatches between what the API expects and what migrations/db-init set up.

## Root Cause

- `docker-compose.dev.yml`'s `db-init` service lacked the `./api:/api:ro` read-only bind mount
  present in `docker-compose.yml`'s equivalent service.
- `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` env vars were inconsistently
  set (or missing) across the dev stack's `api` and `db-init` services.

## Fix

- `docker-compose.dev.yml`:
  - Added `EMBEDDING_DIMENSIONS=${EMBEDDING_DIMENSIONS:-1024}` to the `api` service.
  - Added `EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-ollama}` and
    `EMBEDDING_DIMENSIONS=${EMBEDDING_DIMENSIONS:-1024}` to the `db-init` service (alongside the
    existing `EMBEDDING_MODEL`).
  - Added `./api:/api:ro` to `db-init`'s volumes, mirroring the production/main stack's contract so
    `run_migrations.py` can import `api/config.py`.
- Added a regression test, `api/tests/test_docker_compose_dev.py`, that parses
  `docker-compose.dev.yml` with PyYAML (no Docker daemon required) and asserts:
  - `db-init` mounts `./api:/api:ro`.
  - `api` and `db-init` both carry `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` /
    `EMBEDDING_DIMENSIONS` with the expected `mxbai-embed-large` / `1024` defaults.
  - `api` and `db-init` never disagree on those embedding defaults.

## Acceptance Criteria

- [x] `db-init` in `docker-compose.dev.yml` mounts `./api:/api:ro` so `run_migrations.py` can
      import `api/config.py`, matching `docker-compose.yml`'s contract.
- [x] `api` and `db-init` in `docker-compose.dev.yml` both set `EMBEDDING_PROVIDER`,
      `EMBEDDING_MODEL`, and `EMBEDDING_DIMENSIONS` with identical defaults
      (`ollama` / `mxbai-embed-large` / `1024`).
- [x] Regression test lives in `api/tests/test_docker_compose_dev.py` and is collected by the
      standard `cd api && pytest tests/` suite (no separate test entry point under `scripts/`).
- [x] `docker-compose.dev.yml` still validates via `docker compose ... config` using a temporary
      env file derived from `.env.dev.example` (since `.env.dev` is a local, gitignored file not
      present in every checkout).
- [x] No production files (`docker-compose.yml`, `azure-deploy.yml`, etc.) changed.

## Verification

```bash
# Targeted regression test
.venv/bin/python -m pytest api/tests/test_docker_compose_dev.py -q

# Full API suite still collects it
cd api && python -m pytest tests/ -k docker_compose_dev -q

# Compose file validates without Docker being started, using a throwaway env file
tmp=$(mktemp)
cp .env.dev.example "$tmp"
docker compose -p getinspired-dev --env-file "$tmp" -f docker-compose.dev.yml config >/dev/null
rm -f "$tmp"
```

## Out of Scope

- Changes to `.env.dev` itself (local file, not tracked in this worktree; user's actual file is
  already correct).
- Changes to the production/main stack (`docker-compose.yml`) — already correct and used as the
  reference contract.

## Related

- `docker-compose.yml`'s `db-init` service — the reference contract this story brings the dev
  stack's `db-init` in line with.
- `scripts/migrations/run_migrations.py` — the script whose `../../api` import path requires the
  `/api` mount.
- `docs/LOCAL_DEVELOPMENT.md` — documents the `make docker-up-dev` workflow this story fixes.
