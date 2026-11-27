---
id: BITB-351
status: todo
priority: P3
kind: nfr
milestone: R1
size: XS
created: 2026-11-19
---

# BITB-351: Public Church-Finder 502 Discloses the Upstream HTTP Status Code

**Prompted by:** BITB-317 verification (follow-up).

## Problem

`api/routes/church.py:116-118` answers a failed upstream call with a public 502 whose detail
interpolates the upstream response status:

```python
detail=f"Church finder service returned an error: {e.response.status_code}",
```

The endpoint is public (rate-limited by BITB-298, not authenticated). The disclosure is mild — a
status code, with no host, credential or SQL content — which is why BITB-317 left it alone: it is
not `str(e)` and so falls outside that story's acceptance criterion.

It matters for two reasons:

1. It tells an anonymous caller how the upstream dependency is failing (401/403 vs 429 vs 5xx),
   which distinguishes "our key is rejected" from "we are being throttled".
2. It is the one surviving `detail=f"...{e...}"` shape in `api/routes/`, so it is the reason the
   BITB-317 static guard cannot be widened to catch exception interpolation (see BITB-349). Fixing
   it unblocks the stricter guard.

## Requirements

- Return a fixed, non-identifying detail (in the style of the BITB-307 upstream message and the
  neighbouring 500 branches), e.g. `"Church finder service is temporarily unavailable."`.
- Log the upstream status code and URL at WARNING so operators keep the signal.
- Keep the 502 status code and the response shape unchanged.
- Check the web and Android clients first: if either renders this `detail` to the user, the
  replacement string must go through the normal i18n path for all 11 languages rather than be a
  bare English string.

## Tests

- Upstream returning 503 → the public body does not contain `"503"`; the log does.
- The 502 status code and body keys are unchanged.

## Acceptance criteria

- [ ] No public response under `api/routes/` interpolates an exception or upstream status into its detail
- [ ] The upstream status code is still recoverable from logs
- [ ] BITB-349's widened guard can be enabled without an exemption for `church.py`

## Related

BITB-317 (redacted the `/health/ready` leak), BITB-349 (stricter guard this unblocks), BITB-307 (generic upstream errors), BITB-298 (rate-limited this endpoint).
