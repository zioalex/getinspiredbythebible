# BITB-155: In-cluster CoreDNS watchdog with failure-time diagnostics

**Status:** 🎯 Todo | **Priority:** P1 | **Size:** S | **Date:** 2026-09-19

## Problem

On 2026-09-19 cluster DNS stopped resolving external names. Agents failed with
`curl: (6) Could not resolve host`, and CoreDNS logged upstream timeouts to both
`192.168.178.1` and `8.8.8.8`. Restarting the CoreDNS deployment fixed it.

The root cause was never established, and that is the actual problem. By the
time anyone looked, the evidence had to be reconstructed. What was gathered
afterwards does not fit a single mechanism:

* a fresh pod, bypassing CoreDNS entirely, could not do UDP/53 to `8.8.8.8` --
  so CoreDNS's own logic was not the fault
* the same pod reached `1.1.1.1:443` over TCP and pinged the LAN gateway, so pod
  egress was not broken generally
* the node resolved fine against both upstreams
* flannel's `MASQUERADE` rule in `FLANNEL-POSTRTG` was present and correct

Conntrack exhaustion would have taken the TCP probe down too. Stale conntrack
entries do not explain a fresh source port to a different upstream. The known
`nf_nat` / `--random-fully` UDP race produces intermittent stalls, not a total
outage. Restarting CoreDNS should not have fixed a node-level UDP problem, but
it did.

CoreDNS's own liveness (`/health`) and readiness (`/ready`) probes stayed green
throughout: they check the process and its plugins, never that forwarding
actually resolves anything. A wedged-but-alive CoreDNS is invisible to them.

The existing `prod-monitor.yml` cannot cover this -- it runs in GitHub Actions
and cannot reach the homelab LAN.

## Acceptance criteria

* Probes cluster DNS end-to-end (resolves an external name through CoreDNS) on a
  fixed interval, in-cluster
* On failure, captures a diagnostic bundle **at failure time** in one structured
  log line: cluster-DNS result, direct UDP/53 to upstream, a TCP control probe,
  and an internal-name resolution -- enough to name the broken layer without
  reconstruction
* Emits a Kubernetes `Warning` Event so the failure is visible to
  `kubectl get events` and anything watching the API
* Restarts the CoreDNS deployment after N consecutive failures, gated by an
  `AUTO_RESTART` env var and rate-limited by a cooldown so it cannot loop
* Least-privilege RBAC: patch limited to the `coredns` deployment by
  `resourceNames`, plus event creation. No other write verbs
* Recovery is logged and Evented too (fail -> pass transition), not just failure
* Static tests assert the RBAC is not over-broad, the probe covers all four
  legs, and the cooldown/threshold are wired -- runnable in CI with no cluster
* `yamllint` + `shellcheck` + `markdownlint` clean

## Scope

`k8s/dns-watchdog/`, `scripts/test_dns_watchdog.py`, Makefile target, CI wiring.

## Out of scope

Root-causing the UDP/53 egress failure itself. This story makes the next
occurrence diagnosable; it does not claim to explain the last one.
