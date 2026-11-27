---
id: BITB-348
status: todo
priority: P3
kind: chore
milestone: R1
size: XS
created: 2026-11-19
depends_on: [BITB-317]
---

# BITB-348: Nothing Pins `/health` as Local-Access-Only, So the Redacted Error Paths Can Silently Re-Open

**Prompted by:** BITB-317 build (follow-up).

## Problem

BITB-317 stopped the public `/health/ready` probe from echoing the raw database exception, but it
deliberately left the detailed error text in place for the three other component checks:

- `check_llm_health()` — `error=str(e)` (`api/routes/health.py`, `ProviderError` and generic branches)
- `check_embedding_health()` — `error=str(e)` (same two branches)
- `get_memory_info()` — `return {"error": str(e)}`

That is safe **only** because those values surface through `GET /health`, which carries
`dependencies=[Depends(require_local_access)]` (`api/routes/health.py:205`), and
`require_local_access` raises 403 for a non-local client (`api/utils/local_only.py`).

**Nothing in the test suite asserts that guard at the route level.** Verified 2026-11-19: every
test that calls `GET /health` (`test_api.py:65`, `test_middleware.py`, `test_access_audit.py:139`)
goes through a `local_client` fixture, and no test asserts a non-local client gets 403 from
`/health`. `require_local_access` itself is unit-tested (`test_utils_coverage.py`,
`test_client_ip.py`), but the *wiring* is not. Deleting or reordering the dependency on the
`/health` route would therefore pass CI green while re-opening the exact leak BITB-317 closed —
on three more components plus memory info, which can carry provider endpoints and keys in
exception text.

## Requirements

- A route-level test asserting `GET /health` returns 403 for a non-local client IP.
- A test asserting the detailed (`str(e)`) component error text is reachable **only** through that
  guarded route — i.e. it never appears in a `/health/ready` or `/health/live` response.
- Keep the existing local-client `/health` tests passing unchanged.

## Acceptance criteria

- [ ] Removing `dependencies=[Depends(require_local_access)]` from the `/health` route makes a test fail
- [ ] A test covers the non-local 403 path for `/health` specifically (not just the `require_local_access` unit)

## Related

BITB-317 (the redaction this guard protects), BITB-307 (generic upstream errors), BITB-297 (trusted client IP).
