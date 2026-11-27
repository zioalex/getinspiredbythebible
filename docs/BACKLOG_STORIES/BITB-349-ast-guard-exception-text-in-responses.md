---
id: BITB-349
status: todo
priority: P3
kind: chore
milestone: R1
size: S
created: 2026-11-19
depends_on: [BITB-317]
---

# BITB-349: The Exception-Text Guard Is a Text Scan and Misses f-String Interpolation Forms

**Prompted by:** BITB-317 build (follow-up).

## Problem

BITB-317 added a regression guard in `api/tests/test_health_ready_error_redaction.py` that scans the
source of the public route modules for `detail=str(e)` (and, inside `readiness_probe` only, for
`error=str(e)` / `"error": str(e)`). It is a plain-text regex scan, so it catches only the exact
spelling it was written for. It does not catch:

- f-string interpolation: `detail=f"... {e}"`, `detail=f"{type(e).__name__}: {e}"`
- a renamed binding: `except Exception as exc: ... detail=str(exc)`
- the value travelling through a local first: `msg = str(e)` … `detail=msg`
- exception text reaching a response from a helper in `api/utils/` rather than from `api/routes/`

The module scan also cannot check `"error": str(e)` at all, because `feedback.py` legitimately
*logs* `extra={"error": str(e)}` — a text scan cannot tell a log call from a response body, so that
pattern had to be dropped for whole modules.

There is already at least one live interpolation form the current guard would not flag:
`api/routes/church.py:118` returns `detail=f"Church finder service returned an error: {e.response.status_code}"`.
A status code is harmless, which is why BITB-317 left it, but the shape is exactly what the guard
is blind to, so the next one will not be caught either.

## Requirements

- Replace the text scan with an AST-based check (`ast.walk`) over **all** of `api/routes/*.py`
  that flags exception-derived values reaching a response, covering `HTTPException(detail=...)`,
  `JSONResponse(content=...)` and returned dict literals.
- Distinguish a response from a log call, so `logger.*(..., extra={"error": str(e)})` stays allowed
  without having to drop the pattern wholesale.
- Allow an explicit, commented exemption list for routes guarded by `require_local_access` rather
  than exempting whole modules by name.
- Keep it fast enough for the unit-test tier (no network, no DB).

## Acceptance criteria

- [ ] The guard flags `detail=f"...{e}"` and `detail=str(exc)` forms, proven by a fixture the test parses
- [ ] The guard covers every module under `api/routes/`, with exemptions named per-route, not per-module
- [ ] `logger.warning(..., extra={"error": str(e)})` does not trip it
- [ ] The BITB-317 text-scan tests are replaced by the AST guard, not kept alongside it

## Related

BITB-317 (added the text scan), BITB-307 (generic upstream errors).
