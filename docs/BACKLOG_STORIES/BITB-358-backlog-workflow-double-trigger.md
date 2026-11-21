---
id: BITB-358
status: todo
priority: P2
size: S
created: 2026-11-21
---

# BITB-358: Backlog Workflow Double-Trigger Cancels Its Own Twin and Blocks PR Merges

**Prompted by:** PRs #1324 and #1325 on 2026-11-21: for each PR event the `Backlog`
workflow (`.github/workflows/backlog.yml`) started TWO instances in the same second
(runs 44894868206/44894868915 on #1324; 44897984705/44897986943 on #1325); the
workflow's `concurrency` cancelled one twin, and the merge gate read the CANCELLED
instance as the latest run for `Detect backlog-related changes`, `BACKLOG.md Stub
Guard (BITB-313)` and `Backlog Front-Matter Check (BITB-313)` — `mergeStateStatus:
BLOCKED` despite a green twin. A manual `gh run rerun` of the cancelled run unblocked
both PRs.

## Problem

Every PR can be merge-blocked by a self-cancelling duplicate run of its own backlog
guards; recovery requires a manual rerun that someone must notice. The same
push+pull_request double-run exists for `Pre-Commit Validation` (both instances green,
so harmless today — but it is the same class the impaginai repo fixed by restricting
push triggers to `main`).

## Acceptance criteria

- [ ] The `Backlog` workflow starts exactly one run per PR event: diagnose the double
      trigger (duplicate `on:` keys, a `workflow_run` + `pull_request` overlap, or
      missing event dedupe) and remove it; no self-cancelling twins
- [ ] Push-triggered workflow double-runs on PR branches are deduped (push trigger
      restricted to `main`, or an equivalent guard) for the affected workflows
- [ ] A PR with backlog-story changes reports all three guards green and
      `mergeStateStatus` clean without any manual `gh run rerun`

## Related

BITB-313, BITB-165.
