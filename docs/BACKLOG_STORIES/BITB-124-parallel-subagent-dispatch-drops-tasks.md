# BITB-124: Parallel Subagent Dispatch Silently Drops Tasks

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S (< 4 hrs to characterise; fix size unknown — may be upstream)
**Created:** 2026-09-12
**Related:** BITB-123 (agent graph), PR #1042

---

## Problem

When the orchestrator dispatches two independent subagent tasks **in the same
message** (the documented default in `AGENTS.md` → "Launch multiple agents
concurrently whenever possible"), one of them can come back as
`Task cancelled` without ever running.

Observed during the delegation smoke test on PR #1042:

| Dispatch | Agent | Result |
| -------- | ----- | ------ |
| Parallel (2 in one message) | `android-expert` | ✅ completed |
| Parallel (same message) | `fullstack-engineer` | ❌ `Task cancelled` |
| Serial (retry, alone) | `fullstack-engineer` | ✅ completed |

The same agent succeeded immediately when dispatched on its own, so this is a
dispatch/concurrency fault, not an agent definition, model, or auth problem.
(It was initially mistaken for an auth issue because it coincided with an
unauthenticated `gh`; authenticating did not change the behaviour.)

## Why it matters

This is a **silent correctness failure in the coordination layer**, which is
worse than a loud one:

- The orchestrator's documented best practice is to batch independent
  delegations. If batching drops work, the recommended pattern is the unsafe
  one and the safe pattern is the one we tell agents not to use.
- A dropped task returns a terminal-looking `Task cancelled` rather than an
  error, so an orchestrator may treat the subtask as deliberately abandoned and
  carry on — reporting success for work that never happened.
- It is load-dependent and therefore intermittent: it will not reproduce
  reliably in a quick check, and will bite hardest on the large fan-out
  delegations the 12-agent graph exists to enable.

## Acceptance Criteria

- [ ] Reproduce deterministically: script N parallel dispatches, record the
      cancellation rate over repeated runs
- [ ] Determine the layer at fault — opencode task tool, the
      `opencode-runtime-fallback` plugin, provider rate limiting (429), or the
      KubeOpenCode agent runtime
- [ ] Confirm whether it correlates with shared-model contention (several
      agents in `opencode.json` share `opencode/nemotron-3-ultra-free`) or with
      the plugin's `max_fallback_attempts` / `cooldown_seconds` settings
- [ ] Either fix, or document a concurrency ceiling and make the orchestrator
      respect it
- [ ] A cancelled task must surface as a **retryable error**, never as a
      silent terminal state
- [ ] If the root cause is upstream, file the issue and link it here

## Notes / Leads

- All agents share one provider (`opencode`) with `setCacheKey: true` and a
  600s timeout (`scripts/generate-opencode-config.py` → `PROVIDER`).
- The runtime-fallback plugin retries on `[429, 500, 502, 503, 504]` with
  `max_fallback_attempts: 1` and `cooldown_seconds: 120`. A concurrent 429
  where the single fallback attempt is already spent is a plausible path to a
  task ending as cancelled rather than retried.
- Cheapest first experiment: give the two agents *different* primary models and
  re-run the parallel dispatch. If the cancellation disappears, it is provider
  contention rather than the task tool.
