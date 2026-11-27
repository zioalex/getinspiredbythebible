---
id: BITB-347
status: todo
priority: P3
kind: chore
size: XS
created: 2026-11-19
---

# BITB-347: `docs/SECURITY.md` Limits Table Is Stale — Wrong Session Cap, No Per-Scope Limits

**Prompted by:** BITB-310 verification (finding 3).

## Problem

The "Limits" table in `docs/SECURITY.md` has drifted from the code:

- It states a session lifetime limit of **100** (`docs/SECURITY.md:155`), and the sample env
  block repeats it as `RATE_LIMIT_SESSION_MAX_REQUESTS=100` (`:258`). `api/config.py` has
  `rate_limit_session_max_requests: int = 10`. The documented number is 10× the real one, in
  two places. Note `/config` publishes the real cap to clients, so the doc is the only thing
  that is wrong.
- It lists none of the six per-scope IP limits introduced by BITB-298 and extended since:
  `RATE_LIMIT_SEARCH_PER_MINUTE` (30), `RATE_LIMIT_FEEDBACK_PER_MINUTE` (20),
  `RATE_LIMIT_CONTACT_PER_MINUTE` (3), `RATE_LIMIT_CHURCH_PER_MINUTE` (6),
  `CHAT_FINALIZE_RATE_LIMIT_PER_MINUTE` (10), `RATE_LIMIT_TELEMETRY_PER_MINUTE` (60).

Anyone reading `SECURITY.md` to answer "what are we rate-limited to?" gets a wrong answer for
chat and no answer for every other endpoint. `scripts/env-manifest.yaml` is the declared source
of truth and is correct, so this is a documentation defect only — no code change is needed.

This is pre-existing drift (BITB-298 added the scopes without touching the table); BITB-310
added the sixth scope without fixing it either, and filed this instead.

## Requirements

1. Correct the session lifetime row (`:155`) **and** the sample env block (`:258`) to 10, or
   state the setting name rather than a number so it cannot drift again.
2. Add a row per scope, each naming its env var, so the table matches
   `scripts/env-manifest.yaml`.
3. Prefer naming env vars over hardcoding values, so a default change does not re-stale the doc.
4. Re-scan the rest of `SECURITY.md` for the same class of drift while in there, per AGENTS.md
   *Documentation Completeness* ("when you touch the README at all, re-scan it").

## Tests

Documentation-only. If a cheap guard is practical, a test asserting every
`RATE_LIMIT_*_PER_MINUTE` key in `scripts/env-manifest.yaml` appears in `docs/SECURITY.md`
would stop the next drift; otherwise none.

## Acceptance criteria

- [ ] Session lifetime limit no longer contradicts `api/config.py`
- [ ] All six per-scope IP limits documented with their env var names
- [ ] No other stale numbers found in `docs/SECURITY.md`, or they are fixed too

## Related

BITB-298, BITB-310, BITB-320 (chat finalize limit), BITB-307.
