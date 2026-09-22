# BITB-160: Cluster triage collector and runbook

**Status:** 🎯 Todo | **Priority:** P2 | **Size:** S | **Date:** 2026-09-19
**Renumbered:** 2026-09-21 from BITB-156 — ID collision with the Android session-limit story (#1083), which claimed BITB-156 first

## Problem

The 2026-09-19 outage took most of a day and produced five wrong diagnoses
before the right one: a NetworkPolicy selector, "policies cannot affect another
namespace", a conntrack NAT race, a stale ipset, and stale kube-router chains.
Each was plausible, each was wrong, and each cost a round trip to disprove.

The pattern is the point. Every wrong turn came from reasoning about what the
manifests *should* do. Every real answer came from runtime state, and each
arrived in a single command:

* which pod owned `10.42.0.9` -- one `kubectl get pods -o wide`
* what a `503` actually meant -- one `curl` against the endpoint, whose body
  named the failing call and address outright
* whether the fault was ours -- one probe pod in a namespace no policy touches
* where DNS packets died -- one `tcpdump` on both sides of the hop
* what governed a pod -- one dump of its `KUBE-POD-FW-*` chain

Two real faults hid behind that noise: an upstream resolver silently not
answering while CoreDNS picked upstreams at random, and `default-deny-all`
applied while the policy that grants the gateway egress was deleted -- the
second self-inflicted mid-debug, because cluster state was not re-read before
issuing the instruction that changed it.

Nothing in the repo captures any of this. The next incident starts from a
conversation instead of a command.

## Acceptance criteria

* One collector gathers cluster state in a single pass, tolerating per-command
  failure (during an incident, half of them fail by design)
* It resolves a pod by IP, since every error carries one and that step is the
  cheapest and most skipped
* It gathers **enforced** state (`iptables`, `ipset`) alongside **declared**
  state (`kubectl get`) -- the gap between them is where the bugs live
* It never renders Secret values; names only
* A runbook orders the checks cheapest-and-most-decisive first, and records the
  traps already paid for: ClusterIP `ipBlock` rules unmatchable post-DNAT,
  `namespaceSelector` needing `kubernetes.io/metadata.name`, CoreDNS probes that
  never test forwarding, `forward` with multiple upstreams defaulting to
  `policy random`, and kube-proxy REJECTing endpoint-less Services
* The runbook states that `connection refused` **can** be a NetworkPolicy
  (kube-router REJECTs rather than drops) -- believing otherwise ruled out the
  real culprit for several rounds
* Static tests keep all of the above from rotting; `shellcheck`, `yamllint` and
  `markdownlint` clean; wired into CI

## Scope

`scripts/collect-k8s-diagnostics.sh`, `docs/RUNBOOK-CLUSTER-TRIAGE.md`,
`scripts/test_cluster_triage.py`, Makefile targets, CI wiring.

## Out of scope

Automating the ladder. The collector gathers; a human reads. The DNS-specific
rungs are already automated in BITB-159's watchdog diagnostic line.
