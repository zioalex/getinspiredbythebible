---
id: BITB-340
status: todo
priority: P2
kind: chore
size: XS
rank: 196
created: 2026-11-18
---

# BITB-340: `page.test.tsx` Leaves a Chat Submit Running After Teardown — Intermittent Red Frontend CI

**Prompted by:** PR #1300. Its `Frontend Tests (26.x)` job went red twice with no frontend change in
the PR (runs 43993633386 on 2026-11-17 and 44206155597 on 2026-11-18). Both times, every one of the
1799+ tests passed. The job failed only because Vitest caught one unhandled rejection.

## Problem

```
Failed to send message: ReferenceError: window is not defined
Unhandled Rejection: ReferenceError: window is not defined
 ❯ submitMessage src/app/[locale]/ChatIsland.tsx (setIsWarmingUp(false) in the catch block)
 ❯ handleSubmit  src/app/[locale]/ChatIsland.tsx
This error originated in "src/app/[locale]/page.test.tsx"
```

A `submitMessage` started by a test in `frontend/src/app/[locale]/page.test.tsx` is still awaiting
its stream when the jsdom environment is torn down. When it resumes, its `try` body touches
`window`, and the `catch` path calls `setIsWarmingUp` / `setMessages`. React's
`resolveUpdatePriority` reads `window.event`, so the cleanup throws again as an unhandled rejection.
The test-file teardown order decides whether it happens, so it is intermittent and hits unrelated
PRs. In the 2026-11-18 log the last messages before the error were the BITB-118 session-limit tests
(`SessionLimitError`), followed by one `ReferenceError` send failure.

## Acceptance criteria

- [ ] Find the test(s) that leave a submit running (e.g. run `npx vitest run 'src/app/[locale]/page.test.tsx' --sequence.shuffle` repeatedly, or log in `afterEach` which test still has an in-flight `streamMessage` generator)
- [ ] Every test that submits waits for the request to settle (`await waitFor(...)` on the final UI state), or the file adds an `afterEach` that unmounts and drains pending stream mocks before teardown
- [ ] Optional hardening in `ChatIsland.tsx`: skip state updates after unmount (an `isMountedRef` guard in `submitMessage`'s `catch`/`finally`); this also protects production when the user navigates away mid-stream
- [ ] 20 consecutive local `npx vitest run` passes with no "Unhandled Errors" section
- [ ] No test is skipped or quarantined to get there

## Related

BITB-118 (session-limit tests), BITB-320 (stream recovery, also touches `submitMessage`).
