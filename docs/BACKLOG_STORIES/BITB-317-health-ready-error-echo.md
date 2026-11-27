---
id: BITB-317
status: todo
priority: P2
kind: nfr
milestone: R1
size: XS
rank: 45
created: 2026-11-15
---

# BITB-317: `/health/ready` Echoes Raw Database Exception Text to Anonymous Callers

**Prompted by:** BITB-307 build (follow-up). BITB-307 made upstream LLM errors generic but
left the health routes alone.

## Problem

`GET /health/ready` (`api/routes/health.py`, `ready` handler) is public — the platform
readiness probe calls it without credentials — and on a database failure its `503` body
includes `"error": db_health.error`. `check_database_health()` sets that to `str(e)` of the
raw driver exception, which can carry the database host name, port, user name or SQL
fragments. Same pattern (`error=str(e)`) appears in the LLM/embedding checks and
`_get_memory_info()`, but those only surface through `GET /health`, which is already
`require_local_access`-guarded.

## Requirements

- `/health/ready` returns a fixed, non-identifying error string (e.g. `"database unavailable"`
  or `"database check timed out"`); the full exception stays in the log.
- `/health` (local-access only) may keep the detail.
- Readiness semantics (status codes, timeout) are unchanged.

## Tests

- DB check raising an exception containing a sentinel host string → `/health/ready` body
  does not contain it; the log does.
- Timeout path still returns `503` with the timeout message.

## Acceptance criteria

- [ ] No `str(e)` reaches a response of a non-local-access route under `api/routes/`
- [ ] Readiness probe behaviour unchanged (existing health tests green)

## Related

BITB-307 (generic upstream errors), July audit O5.
