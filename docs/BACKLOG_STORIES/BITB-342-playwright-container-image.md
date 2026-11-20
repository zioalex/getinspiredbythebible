---
id: BITB-342
status: todo
priority: P2
size: S
created: 2026-11-18
---

# BITB-342: Run the Playwright Matrix in the Official Playwright Container Image

**Follow-up of:** BITB-341 (deferred there as out of scope)

## Problem

BITB-341 made `playwright install --with-deps` survive a slow Ubuntu mirror (retry + bounded
per-attempt timeout + binary cache + more job headroom). That is mitigation, not elimination: every
`Frontend E2E` leg still apt-installs ~40-100 system packages on a cold cache, so a bad mirror day
still costs minutes per leg and can still, in the limit, exhaust the budget.

`mcr.microsoft.com/playwright:v<version>-noble` ships every engine *and* its system libraries
pre-baked. Running the matrix as a container job removes the apt step and the browser download
entirely — the failure mode BITB-341 mitigates stops existing.

## Why it was not done in BITB-341

The image tag must match the `@playwright/test` version in `frontend/package-lock.json`, or
Playwright refuses to launch ("Executable doesn't exist ... browser revision mismatch"). That
couples a workflow constant to a Dependabot-managed dependency: a `@playwright/test` bump that does
not also bump the tag turns the whole matrix red. Mitigating that needs its own guard, so it was
kept out of a CI-stability hotfix.

## Fix sketch

- Add `container: mcr.microsoft.com/playwright:v<X.Y.Z>-noble` to the matrix job; drop the
  `playwright install*` steps and the `~/.cache/ms-playwright` cache.
- Keep `actions/setup-node` only if the image's Node is not the version the build needs; otherwise
  drop it and keep the npm cache.
- Guard the coupling: a test that reads the image tag out of the workflow and the resolved
  `@playwright/test` version out of `frontend/package-lock.json` and asserts they match, with a
  failure message naming both files. Extend `api/tests/test_frontend_e2e_workflow.py` (BITB-341).
- Teach Dependabot (or the guard's failure text) that a `@playwright/test` bump needs the tag bumped
  in the same PR.

## Acceptance criteria

- [ ] The e2e matrix runs in the official image with no `playwright install` step
- [ ] A test fails, with an actionable message, when the image tag and the lockfile's
      `@playwright/test` version diverge
- [ ] A deliberate mismatch is proven to fail that test (not just asserted to)
- [ ] Median wall-clock of the e2e matrix is recorded before and after, in this story

## Out of scope

- `prod-browser-smoke.yml`: it is a scheduled single-engine job against production; revisit only if
  it keeps timing out after BITB-341.
