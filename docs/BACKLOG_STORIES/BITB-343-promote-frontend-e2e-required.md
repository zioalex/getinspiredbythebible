---
id: BITB-343
status: todo
priority: P2
kind: chore
size: XS
created: 2026-11-18
---

# BITB-343: Promote `Frontend E2E` to a Required Check

**Follow-up of:** BITB-341. **Completes:** BITB-250's open goal.

## Problem

`frontend-e2e.yml` carries its own TODO — "Not a required check yet; make it required once it has
been stable for a while" — and BITB-250 shipped it on that understanding. It has never been
promoted, so a genuine cross-browser read-aloud regression can merge unnoticed: the four engines are
exactly the ones whose quirks caused BITB-210, BITB-248 and BITB-249, and nothing blocks on them.

Promotion was blocked in practice by infra flake, not by the specs: BITB-341 documents three runs
cancelled at the job timeout inside `playwright install`. With that fixed, the only thing left is
evidence.

## Fix

1. Collect the evidence after BITB-341 lands: the pass rate of `Frontend E2E` over a window of real
   runs (`gh run list --workflow frontend-e2e.yml`), split by matrix leg, with every non-success
   classified as spec failure / infra flake / concurrency cancel.
2. If the infra-flake count is zero over that window, add `Read-aloud e2e (chromium)`,
   `(firefox)`, `(webkit)` and `(Mobile Safari)` to the branch-protection required checks.
3. Drop the "not a required check yet" comment from the workflow header and point it at this story.

## Acceptance criteria

- [ ] Pass rate recorded in this story, per matrix leg, with each failure classified
- [ ] Owner step: add the four `Read-aloud e2e (...)` checks to `main`'s branch protection
      (repo settings — Claude cannot change branch protection)
- [ ] The stale "not a required check yet" comment is gone from `frontend-e2e.yml`
- [ ] A deliberately broken read-aloud change is confirmed to block a PR

## Notes

Concurrency cancels (`cancel-in-progress: true`, superseded pushes) are normal and must not count
against the pass rate — only the newest run per ref does. Making the check required turns every
remaining flake into a merge blocker, so do not promote on a hunch.
