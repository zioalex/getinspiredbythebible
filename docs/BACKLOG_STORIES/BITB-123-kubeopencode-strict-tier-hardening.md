# BITB-123: KubeOpencode strict-tier sandbox hardening

**Status:** 🎯 Todo | **Priority:** P1 | **Size:** M | **Date:** 2026-09-06

## Problem

Agent sandbox has full egress, LAN-reachable `0.0.0.0:4096` with unauthenticated
`/api/session`, and `OPENCODE_API_KEY` exposed via ENV.

## Acceptance criteria

* Strict egress: public `443/53` OK, RFC1918 + `169.254/16` blocked
* `localhost:11434` Ollama keeps working, LAN opt-in via annotation
* API key via `0400` file mount, `env` clean, `/api/session` requires auth
* Rollout documented, running agents drain via `30m` standby timeout
* `kubeconform` + `yamllint` pass on `k8s/kubeopencode/`
* `scripts/validate-env.py` passes (k8s-only secret kept out of app env manifest)

## Scope

`k8s/kubeopencode/*.yaml`, `docs/SECURITY-KUBEOPENCODE.md`.
