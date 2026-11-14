---
id: BITB-152
status: done
priority: P1
size: M
rank: 520
created: 2026-09-06
prs: [1045, 1086, 1087]
---

# BITB-152: KubeOpencode strict-tier sandbox hardening

**Migration note (2026-11-13, status):** (PR #1045 merged 2026-09-18, hardened by follow-ups #1086/#1087 on the same feature branch before it landed on main)

## Problem

Agent sandbox has full egress, LAN-reachable `0.0.0.0:4096` with unauthenticated
`/api/session`, and `OPENCODE_API_KEY` exposed via ENV.

## Acceptance criteria

* Strict egress: public `443/53` OK, RFC1918 + `169.254/16` blocked
* `localhost:11434` Ollama keeps working, LAN opt-in via annotation
* API key via `0400` file mount, `env` clean, `/api/session` requires auth
* No committed secret value: `opencode-api-key` created imperatively
  (same pattern as the sibling secrets in `deployment/kubeopencode/`)
* Least-privilege agent SA: cannot patch annotations or create NetworkPolicies
  (verified via `kubectl auth can-i`)
* Rollout documented, running agents drain via `30m` standby timeout
* `kubeconform` + `yamllint` pass on `k8s/kubeopencode/`
* `scripts/validate-env.py` passes (k8s-only secret kept out of app env manifest)

## Scope

`k8s/kubeopencode/*.yaml`, `docs/SECURITY-KUBEOPENCODE.md`.
