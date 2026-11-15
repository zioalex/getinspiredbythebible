---
id: BITB-319
status: in-review
priority: P1
size: XS
created: 2026-11-15
---

# BITB-319: Post-Deploy Smoke Tests Fail on `fastapi` Import; API Smoke Suite Never Runs

## Bug report

The `Functional Tests (smoke)` job in deploy run 43655682966 (deploy SHA `e401385`) failed:
all 37 frontend e2e tests errored at setup with `ModuleNotFoundError: No module named 'fastapi'`.
The app itself was fine.

**Root cause.** BITB-298 (PR #1290) added an autouse fixture in `api/tests/conftest.py`
that imports `routes.scripture` (and so FastAPI). The smoke job installs only
`httpx pytest pytest-asyncio pydantic pydantic-settings`, so every e2e/functional test
failed during fixture setup before it touched the live site.

**Second gap.** The `Run functional API tests (backend API)` step has no `if:`, so it was
skipped as soon as the e2e step failed, and the summary misreported this as
"backend URL not available". The live backend was not checked at all on that deploy.

## Fix

- `api/tests/conftest.py`: the limiter-reset fixture becomes a no-op when the app cannot be
  imported (the live-URL suites never use in-process limiters).
- `.github/workflows/azure-deploy.yml`: the functional API step runs with `if: ${{ !cancelled() }}`,
  so the backend suite runs even when the e2e suite fails. The summary text is corrected.

## Acceptance criteria

- [x] Regression test `api/tests/test_conftest_smoke_env.py` blocks `fastapi` in a subprocess and
      runs a test through the real conftest. Fails on `main` with the CI error, passes with the fix.
- [x] `tests/e2e` passes against https://voxquieta.org in a venv with only the smoke job's packages
      (37 passed, 2026-11-15).
- [ ] The next deploy's smoke job is green and both suites run.

## Out of scope

- Android dropping chips and verse references when a stream ends without `completion`: BITB-320.
