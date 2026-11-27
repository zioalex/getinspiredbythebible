---
id: BITB-319
status: in-review
priority: P1
kind: chore
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

**Related tooling bug (same story, reported 2026-11-15).** `make az-logs-backend` failed with
`Got bad status from the logstream API: 500` although the owner was logged in. The bare
`az containerapp logs show --follow` cannot pick a replica when the app is scaled to zero or runs
several replicas. A live stream also cannot show past failures, which is what the investigation
needed.

## Fix

- `api/tests/conftest.py`: the limiter-reset fixture becomes a no-op when the app cannot be
  imported (the live-URL suites never use in-process limiters).
- `.github/workflows/azure-deploy.yml`: the functional API step runs with `if: ${{ !cancelled() }}`,
  so the backend suite runs even when the e2e suite fails. The summary text is corrected.
- New `scripts/az-logs.sh` behind the `make az-logs-*` targets:
  - live tail resolves the latest ready revision + a running replica, explains scale-to-zero,
    and points to the history query on failure;
  - new `az-logs-backend-query` / `az-logs-frontend-query` read past logs from Log Analytics
    (`HOURS`, `LEVEL`, `FILTER`, `LIMIT`, input-validated and KQL-escaped);
  - new `az-chat-stream-errors` gives hourly counts of chat-stream failure signals.
  Documented in `DEPLOYMENT.md` → *Reading production logs*.

## Acceptance criteria

- [x] Regression test `api/tests/test_conftest_smoke_env.py` blocks `fastapi` in a subprocess and
      runs a test through the real conftest. Fails on `main` with the CI error, passes with the fix.
- [x] `tests/e2e` passes against https://voxquieta.org in a venv with only the smoke job's packages
      (37 passed, 2026-11-15).
- [x] `scripts/test_az_logs.py` (fake `az`) covers revision/replica resolution, scale-to-zero,
      the logstream-500 hint, query defaults/options/escaping, input validation and the
      missing-workspace error. `AzureTests.test_log_targets` pins the Makefile wiring.
- [ ] The next deploy's smoke job is green and both suites run.
- [ ] Owner step: `make az-logs-backend` and `make az-logs-backend-query HOURS=6` work against prod.

## Out of scope

- Android dropping chips and verse references when a stream ends without `completion`: BITB-320.
