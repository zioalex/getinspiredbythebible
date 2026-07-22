# BITB-073: Split Dev/Prod Python Requirements (Stop Shipping pytest in the Prod Image)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S (< 4 hrs)
**Created:** 2026-07-20

**As a** maintainer, **I want** test-only Python dependencies out of
`api/requirements.txt`, **so that** the production image doesn't carry the test
framework and the runtime dependency surface (and its CVE scan) reflects what
actually runs in production.

## Context

Finding F3 of the 2026-07-20 360° review (`docs/audits/2026-07-20-360-review.md`):
`api/requirements.txt` includes `pytest==9.1.1` and `pytest-asyncio==1.4.0`, so
every production image build installs them. The fix is mechanical but touches
several files, which is why it's a separate compartment instead of being
bundled with BITB-072.

## Proposed shape

- `api/requirements.txt` — runtime deps only (remove the `# Testing` block).
- `api/requirements-dev.txt` — `-r requirements.txt` + `pytest`,
  `pytest-asyncio` (and any other test/lint tools that later migrate here).

## Touch points (verified by grep)

| File | Change |
|------|--------|
| `api/Dockerfile` | none — keeps installing `requirements.txt` (now runtime-only) |
| `.github/workflows/test_update.yml` | 2× `pip install -r requirements.txt` → `requirements-dev.txt`; 2× `cache-dependency-path` → include both files; `safety check` stays on runtime file (or scans both) |
| `.github/workflows/azure-deploy.yml` | 2× `cache-dependency-path: "api/requirements.txt"` — verify those jobs' install lines and point test-running jobs at `requirements-dev.txt` |
| `Makefile` | `setup-dev` targets (~lines 61, 122) → `requirements-dev.txt`; safety target unchanged |
| `docs/VIRTUAL_ENV.md` / `docs/LOCAL_DEVELOPMENT.md` | update any `pip install -r api/requirements.txt` instructions |

## Acceptance Criteria

- [ ] `pip install -r api/requirements.txt` in a clean venv does **not** install pytest
- [ ] `pip install -r api/requirements-dev.txt` installs everything the test suite needs; `cd api && python -m pytest tests/ -x -q` passes
- [ ] Backend CI jobs (unit + integration) green with the new install lines and cache keys
- [ ] Docker image builds and `/health` passes (image never needed pytest — assert it still installs cleanly)
- [ ] Dependabot pip config still picks up both files (directory-level `pip` ecosystem covers requirements*.txt automatically)
