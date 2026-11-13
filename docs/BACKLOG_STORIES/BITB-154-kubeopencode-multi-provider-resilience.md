# BITB-154: KubeOpenCode Multi-Provider Resilience — Cross-Provider Fallback + Survive Provider Outage

**Status:** 🚧 In Progress (PR #1077)
**Priority:** P1
**Size:** S (config change, already implemented; pending merge + cluster sync)
**Created:** 2026-09-14
**Related:** BITB-123 (agent graph), BITB-124 (parallel dispatch), PR #1066 (Copilot auth)

---

## Problem

The 12-agent graph had a **single-provider fallback chain** and the fallback
plugin ignored **auth/quota 4xx errors**, so a single provider outage (or a
subscription running out of credits) silently broke the coordination layer.

Two distinct defects, both observed live:

1. **Single-provider fallback.** Every agent fell back to
   `opencode/muse-spark-1.3-contributor-free` only. A full OpenCode Zen outage
   would therefore take down the entire graph — including agents whose
   *primary* was GitHub Copilot or OpenRouter, because their fallback still
   pointed back at OpenCode Zen. `max_fallback_attempts` was `1`, so only one
   hop was ever attempted.

2. **Auth/quota errors never triggered fallback.** The
   `opencode-runtime-fallback@0.2.4` plugin retried only
   `[429, 500, 502, 503, 504]`. When GitHub Copilot subscription credits were
   exhausted, the `github-copilot` provider returned a 401/402/403 auth or
   quota error that was **not** in the retry list — so no failover happened and
   the three agents pinned to `github-copilot/claude-opus-5` (orchestrator,
   verifier, risk-auditor) returned **empty responses**.

Observed during a liveness probe:

| Subagent | Primary model | Result |
| -------- | ------------- | ------ |
| `fullstack-engineer` | `opencode/nemotron-3-ultra-free` | ✅ returned content |
| `verifier` | `github-copilot/claude-opus-5` | ❌ empty `<task_result>`, `state=completed` |

## Why it matters

This is a **silent correctness failure in the coordination layer**:

- A failed subagent returns an empty `<task_result>` with `state=completed`,
  so the orchestrator cannot distinguish "provider down" from "no work to
  report" and may treat the missing work as done.
- The three Copilot-pinned agents are the **load-bearing reasoning roles**
  (planning, independent verification, risk audit). Losing them silently
  degrades the Plan → Build → Verify relay exactly where reasoning quality
  matters most.
- A single-provider fallback is a single point of failure for the whole graph.

## Acceptance Criteria

- [x] Every one of the 19 agent slots (12 custom + 7 built-in) has
      `fallback_models` spanning **≥2 providers**
- [x] `orchestrator` / `verifier` / `risk-auditor` primary moved off
      `github-copilot/claude-opus-5` → `opencode/nemotron-3-ultra-free`
- [x] Fallback plugin retries on auth/quota 4xx (`400/401/402/403`) plus
      quota/auth error patterns, not just `[429, 500, 502, 503, 504]`
- [x] `max_fallback_attempts` raised `1` → `2` so the 2-hop chain executes
- [x] Generator tests pass (`19/19`); committed `opencode.json` has no drift
- [ ] PR #1077 merged to `main`
- [ ] Config applied to the live cluster: `make sync-opencode-configmap` +
      `kubectl -n kubeopencode-system delete pod <agent-pod>` (requires write
      RBAC; the in-pod `kubeopencode-agent` SA is read-only)

## Notes / Leads

- **The running pod does not read the repo checkout.** The live process uses
  `OPENCODE_CONFIG=/tools/opencode.json` (a mounted ConfigMap), not
  `/workspace/opencode.json`. Git changes take effect only after
  `make sync-opencode-configmap` + a pod restart.
- **The in-pod SA is read-only.** `kubectl -n kubeopencode-system get configmap
  opencode-config` returns `Forbidden` for `system:serviceaccount:...:kubeopencode-agent`.
  The sync must be run from a machine with cluster write RBAC (the developer's
  workstation, not the agent pod).
- GitHub Copilot wiring is **left intact** in `deployment/kubeopencode/agent.yaml`
  (`github-copilot` credential + `GITHUB_TOKEN` env) so the paid model can be
  re-enabled as a primary (or added as a third fallback hop) when credits return.
- The runtime-fallback plugin is now the *only* thing executing `fallback_models`;
  `make verify-opencode-config` fails if the plugin block disappears.
