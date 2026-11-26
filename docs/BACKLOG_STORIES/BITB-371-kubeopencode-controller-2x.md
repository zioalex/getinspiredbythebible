---
id: BITB-371
status: blocked
priority: P1
size: M
created: 2026-11-26
prs: [1347]
depends_on: [BITB-370]
---

# BITB-371: KubeOpenCode Controller Compatibility with opencode 2.x Agents

## User story

As the owner, I want the KubeOpenCode controller able to run opencode 2.x
agent pods (2.4.2 custom image, BITB-370), so the agent-image migration is
not blocked by controller-side 1.x assumptions.

## Problem (from BITB-370 Phase 1 research, [T-370A], 2026-11-26)

The deployed controller line (v0.1.9, the latest upstream release,
2026-07-19) couples to opencode 1.x in two ways:

1. **Hardcoded health probes**: startup AND readiness probe hit
   `GET /session/status` (`ServerHealthPath`, not spec-expressible). 2.x
   serves `/api/*` routes; if the legacy path is gone, a 2.x agent pod
   never goes Ready and the startup probe kills it at ~62 s (crashloop).
2. **1.x API routes for task submission**: the in-cluster submitter uses
   `POST /session`, `POST /session/:id/prompt_async`, `GET
   /session/status`, `GET /event` — 2.x uses `/api/session`,
   `/api/session/:id/prompt`, `/api/session/active`, `/api/event` with
   `{"data": …}` envelopes. Even a Ready pod would 404 on task submission.

Upstream kubeopencode PR #349 ("feat: support OpenCode 2.x and hermetic
developer environment", xNok, opened 2026-11-22) is the authoritative 2.x
delta — it re-points probes to `/api/info` and adds legacy 404 fallbacks —
but it was **closed unmerged** in favor of a PR on the author's fork
(xNok/kubeopencode). No 2.x support is merged upstream and no release
newer than v0.1.9 exists.

## Dependency note

**Blocked pending the BITB-370 Phase 2 gate result.** The gate boots a
scratch 2.4.2 server and probes the legacy routes empirically:

- If 2.4.2 still serves `/session/status` + legacy routes (unverified
  either way — PR #349's probe re-point is the strongest indirect signal
  they are gone), controller v0.1.9 works unmodified and this story
  collapses to a documentation note.
- If they are gone (expected), this story is the critical path for
  BITB-370 Phases 3-4.

## Options (decision when unblocked)

1. **Wait for upstream kubeopencode support** (merge of PR #349's
   successor or an equivalent) and upgrade the controller + CRDs via the
   standard helm/manifest path. Lowest maintenance, unknown timeline.
2. **Adopt xNok's fork controller** (the closed PR's destination) —
   faster, but runs a fork of the home-cluster control plane.
3. **Patch our controller deployment** (probe path only) if the only
   gap is the health probe — insufficient if task-submission routes also
   404, which the same research indicates.

## Acceptance criteria

- [ ] BITB-370 Phase 2 gate verdict recorded here (legacy routes served:
      yes/no, with the probe evidence)
- [ ] If blocked-on: controller version running 2.x agents identified
      (upstream release / fork / patch) with evidence it re-points probes
      AND task-submission routes
- [ ] Owner step: controller upgraded in the cluster with the standard
      apply order (RBAC + CRDs + deployment, `k8s/kubeopencode/README.md`
      → Apply order)
- [ ] wf3 canary green under the upgraded controller before wf2 touches
      anything (still gated by BITB-370 Phase 3)
- [ ] Rollback path documented (controller version pin + 1.18.31 agent
      image remain mutually compatible)

## Out of scope

- The opencode 2.x config/plugin migration itself (BITB-370)
- Re-architecting probes to be spec-expressible (upstream concern)

## Follow-ups

(none yet)
