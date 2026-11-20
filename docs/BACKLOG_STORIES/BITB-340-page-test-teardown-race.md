---
id: BITB-340
status: in-review
priority: P2
size: XS
rank: 196
created: 2026-11-18
prs: [1322]
follow_ups: [BITB-352]
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

- [x] Find the test(s) that leave a submit running (e.g. run `npx vitest run 'src/app/[locale]/page.test.tsx' --sequence.shuffle` repeatedly, or log in `afterEach` which test still has an in-flight `streamMessage` generator)
- [x] Every test that submits waits for the request to settle (`await waitFor(...)` on the final UI state), or the file adds an `afterEach` that unmounts and drains pending stream mocks before teardown
- [x] Optional hardening in `ChatIsland.tsx`: skip state updates after unmount (an `isMountedRef` guard in `submitMessage`'s `catch`/`finally`); this also protects production when the user navigates away mid-stream
- [x] 20 consecutive local `npx vitest run` passes with no "Unhandled Errors" section
- [x] No test is skipped or quarantined to get there

## Related

BITB-118 (session-limit tests), BITB-320 (stream recovery, also touches `submitMessage`).

## Resolution

Culprit: `Home page responsive layout > responsive header > sends translation=undefined to streamMessage when placeholder is selected` only waited for `streamMessage` to be called, so its submit was still streaming at teardown (found by logging in-flight `abortControllerRef` at unmount; hit in 4 of 8 shuffled runs). The test now waits for the reply and a re-enabled input. The "chips disappear immediately" test deliberately stalls a second turn forever; it never resumes, and the unmount abort now cleans it up.

Fix: `ChatIsland.tsx` gets an `isMountedRef` plus an unmount effect that aborts the in-flight request; `submitMessage` returns early after unmount (post-stream and `catch`, before `console.error`). Regression test: `unmount mid-stream (BITB-340) > aborts the request and swallows a late stream failure after unmount` (fails without the hardening). Second race (found by the verifier): the auto-save effect's `saveFullConversation(...).then(() => setHistoryRefresh(...))` in `ChatIsland.tsx` could resolve after jsdom teardown (originating in `ChatIsland.crisis.test.tsx`, ~1 in 40 runs). It is now guarded by `isMountedRef`; regression test `ChatIsland.unmount.test.tsx` reproduces the exact CI error without the guard.

Verification: 120 consecutive runs of `npx vitest run 'src/app/[locale]/'` with 0 "Unhandled" sections; 2 full-suite runs (86 files, 1854 tests) clean; lint, `tsc --noEmit` and Prettier clean.

## Follow-ups

- BITB-352: `page.test.tsx` tests depend on execution order (`--sequence.shuffle` fails 1–4 tests on `main`).
