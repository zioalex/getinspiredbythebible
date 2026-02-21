# PR: Redesign Functional Tests as Real-User E2E + Backend API Tests

**Status:** In Progress
**Started:** 2026-02-21

## Summary

The original functional tests all skipped in CI because the pre-flight health
check `GET /health/live` returned 404 on the frontend URL
(`https://getinspiredbythebible.ai4you.sh`). The frontend is a standalone
Next.js app with **no API proxy** — the backend is a separate Azure Container
Apps service.

The fix splits the smoke tests into two suites that accurately model the
two-tier architecture and simulate real user behavior:

1. **E2E tests** (`tests/e2e/`) — hit the frontend URL like a real user's
   browser. Test all locale pages load with HTML content.
2. **Functional API tests** (`tests/functional/`) — hit the backend API
   directly using the Azure Container Apps FQDN passed as a CI job output.

## Architecture

```text
User browser
  └── GET https://getinspiredbythebible.ai4you.sh/en   ← E2E tests
        └── Frontend (Next.js) serves HTML/CSS/JS
              └── Browser JS calls NEXT_PUBLIC_API_URL/api/v1/...  ← Functional API tests
                    └── Backend API (Azure Container Apps FQDN)
```

## Changes

- `api/tests/e2e/__init__.py` — new
- `api/tests/e2e/test_frontend_e2e.py` — new (frontend page tests)
- `api/tests/functional/test_production_api.py` — use `BACKEND_API_URL`
- `api/pytest.ini` — add `e2e` marker
- `Makefile` — add `test-e2e`, `test-e2e-local` targets; update `test-functional-local`
- `.github/workflows/azure-deploy.yml`:
  - `deploy` job: add `outputs.backend_url` (exported from Verify Deployment step)
  - `functional-tests` job: run both e2e and functional suites

## Tasks

- [x] Create `tests/e2e/test_frontend_e2e.py` with 20 tests across 4 classes
- [x] Update `tests/functional/test_production_api.py` to use `BACKEND_API_URL`
- [x] Update `pytest.ini` with `e2e` marker
- [x] Add `test-e2e` / `test-e2e-local` Makefile targets
- [x] Update CI: export `backend_url` from deploy job
- [x] Update CI: run both test suites in `functional-tests` job
- [ ] Create PR and verify CI passes

## Notes

- Turnstile bot protection on `/api/v1/chat` means chat E2E tests via browser
  automation (Playwright) would require solving the CAPTCHA challenge. The
  `TestChatEndpointValidation` tests in `functional/` only validate request
  structure (4xx validation errors), not actual LLM responses.
- `BACKEND_API_URL` is exported from the `deploy` job's "Verify Deployment"
  step — no Azure credentials needed in the `functional-tests` job.
- Backward-compat: `FUNCTIONAL_TEST_URL` still works as a fallback alias for
  `BACKEND_API_URL` in the functional tests.
