---
id: BITB-317
status: in-progress
priority: P2
size: XS
rank: 45
created: 2026-11-15
follow_ups: [BITB-348, BITB-349, BITB-350, BITB-351]
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

- [x] No `str(e)` reaches a response of a non-local-access route under `api/routes/`
- [x] Readiness probe behaviour unchanged (existing health tests green)

## Follow-ups

Filed with this story's PR:

- **BITB-348** — nothing pins `/health` as local-access-only, so the three component checks that
  deliberately keep `error=str(e)` could silently become public again.
- **BITB-349** — the static guard added here is a text scan; it misses `detail=f"...{e}"`
  interpolation and other re-introduction forms. An AST check over all of `api/routes/` is sturdier.
- **BITB-350** — `make venv` has no Python version floor (`Makefile` uses bare `python3`), so it
  builds an unusable 3.11 virtualenv where `python3` predates the `requires-python = ">=3.12"` floor.
- **BITB-351** — `api/routes/church.py` still interpolates the upstream HTTP status code into a
  public 502 detail. Not `str(e)`, so out of scope here, but it is why BITB-349's widened guard
  needs an exemption until it is fixed.

## Related

BITB-307 (generic upstream errors), July audit O5.
