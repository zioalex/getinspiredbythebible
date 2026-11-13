# BITB-092: Fix Dev Stack `db-init` Migration Failure and Embedding Config Drift

**Status:** ✅ Done
**Priority:** P1
**Size:** S
**Created:** 2026-08-09
**Completed:** 2026-08-09 (follow-up permission fix also completed 2026-08-09)

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

## Follow-up: `db-init` Permission Failure Writing Downloaded Translations (2026-08-09)

### Problem

After the fix above, `make docker-up`/`make docker-up-dev` still failed on a fresh `./data`
checkout: `db-init` runs as non-root UID 1000 (`api/Dockerfile`), while the host-owned bind mount
`./data` was owned by a different host UID (observed: 1002). `scripts/load_bible.py` successfully
**downloaded** KJV from its source URL, then crashed writing
`/data/bible/translations/kjv.json` with a `PermissionError` — the container user couldn't write
into the host-owned directory it didn't own, even though the mount itself was read-write.

### Root Cause

- `docker-compose.yml`/`docker-compose.dev.yml`'s `db-init` mounted `./data:/data` read-write, but
  db-init's non-root container UID doesn't necessarily match (and can't be assumed to match) the
  host UID that owns `./data` on every developer machine.
- `scripts/load_bible.py`'s `download_translation()` always wrote newly-downloaded translation
  JSON straight back into `data/bible/translations/`, with no alternative writable location
  configurable for container use.

### Fix

- **`scripts/load_bible.py`**: added `resolve_bible_data_path(translation_code, primary_path)`,
  a small typed helper (independently unit-testable, no I/O side effects beyond `Path.exists()`)
  that decides where to read/write a translation's JSON:
  1. The committed `data/bible/translations/<code>.json` source file always wins when it exists —
     this keeps manual-only translations (Hindi, Luther 1912, no download URL) working exactly as
     before, since they have no other source.
  2. If it's missing and the new optional `BIBLE_DOWNLOAD_CACHE_DIR` env var is set, downloads are
     written to `<BIBLE_DOWNLOAD_CACHE_DIR>/<code>.json` instead.
  3. If it's missing and `BIBLE_DOWNLOAD_CACHE_DIR` is unset, falls back to the primary path — the
     historical bare-host default, unchanged for anyone running the script directly (no Docker).
  - No permission errors are silently caught; explicit configuration is expected to prevent them
    in containers, and `download_translation()`'s actual file write still raises normally if the
    resolved path turns out not to be writable.
- **`docker-compose.yml`** and **`docker-compose.dev.yml`** (`db-init` service, both stacks — the
  main stack has the identical UID-mismatch exposure):
  - Changed `./data:/data` to `./data:/data:ro` — db-init never needs to write into the committed
    source tree.
  - Added `BIBLE_DOWNLOAD_CACHE_DIR=/tmp/bible-translations` so first-run downloads (e.g. KJV) land
    in the container's own writable filesystem instead. This cache is ephemeral by design: source
    data is re-downloadable, and `db-init` skips the whole load step on restart once verses are in
    the database (`scripts/init-db.sh`'s `VERSE_COUNT` check).
  - This is local-stack (`make docker-up`/`make docker-up-dev`) configuration only; no production
    deployment file (`azure-deploy.yml`, etc.) was touched.
- **Tests:**
  - `api/tests/test_load_bible_data_path.py` (new) — unit tests for `resolve_bible_data_path()`
    and `download_translation()`: existing committed/source path wins even when a cache dir is
    configured; a missing source uses the configured cache; a missing source with no cache
    preserves the default path; a download (HTTP mocked, no network) writes to the resolved
    writable path and never touches the primary directory.
  - `api/tests/test_docker_compose_bible_cache.py` (new) — parses both `docker-compose.yml` and
    `docker-compose.dev.yml` with PyYAML (no Docker daemon needed) and asserts `db-init` mounts
    `./data:/data:ro` (and not read-write) and sets
    `BIBLE_DOWNLOAD_CACHE_DIR=/tmp/bible-translations` in both stacks, plus a sanity check that the
    pre-existing `./api:/api:ro` mount is unaffected.

### Acceptance Criteria (follow-up)

- [x] A fresh `make docker-up` or `make docker-up-dev` can download KJV without writing into the
      host-owned `./data` bind mount, regardless of host/container UID mismatch.
- [x] Committed manual-only translations (Hindi, Luther 1912) remain loadable unchanged — they
      still read directly from `data/bible/translations/*.json`.
- [x] No chmod/chown/root workaround; no silent catching of `PermissionError`.
- [x] `docker-compose.yml` and `docker-compose.dev.yml` both mount `./data:/data:ro` and set
      `BIBLE_DOWNLOAD_CACHE_DIR=/tmp/bible-translations` for `db-init`.
- [x] Regression tests added and passing:
      `.venv/bin/python -m pytest api/tests/test_load_bible_data_path.py api/tests/test_docker_compose_bible_cache.py -q`
- [x] Both compose files still validate via `docker compose ... config` using throwaway env file
      copies (`.env.local.example` / `.env.dev.example`), without starting/stopping containers.
- [x] `.env.dev` (local, gitignored) left untouched.

### Verification (follow-up)

```bash
# Targeted regression tests
.venv/bin/python -m pytest api/tests/test_load_bible_data_path.py \
  api/tests/test_docker_compose_bible_cache.py api/tests/test_docker_compose_dev.py -q

# Compose config validates for both stacks (throwaway env copies, no containers started)
cp .env.local.example /path/to/scratch/env.local.tmp
docker compose -f docker-compose.yml --env-file /path/to/scratch/env.local.tmp config >/dev/null
cp .env.dev.example /path/to/scratch/env.dev.tmp
docker compose -f docker-compose.dev.yml --env-file /path/to/scratch/env.dev.tmp config >/dev/null

# Manual container-level proof (UID 1000, read-only /data bind mount): a missing translation
# resolves to BIBLE_DOWNLOAD_CACHE_DIR and writes succeed there, while a direct write attempt to
# the read-only /data mount still raises PermissionError/OSError as expected; a committed
# manual-only translation (hindi.json) is still read directly from the read-only primary path.
```
