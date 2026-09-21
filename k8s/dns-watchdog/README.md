# DNS watchdog (BITB-159)

In-cluster watchdog that probes cluster DNS end-to-end on an interval,
captures a four-leg diagnostic bundle **at failure time**, emits Kubernetes
Events, and optionally restarts the CoreDNS deployment after sustained
failure. Built after a 2026-09-19 incident where CoreDNS stopped forwarding
upstream while its own `/health` and `/ready` probes stayed green, and the
evidence needed to root-cause it had to be reconstructed after the fact.

See `docs/BACKLOG_STORIES/BITB-159-coredns-dns-watchdog.md` for the incident
writeup and acceptance criteria.

## Deploy

```bash
kubectl apply -f serviceaccount-watchdog.yaml -f role-watchdog.yaml \
  -f rolebinding-watchdog.yaml -f configmap-watchdog.yaml -f deployment.yaml
```

Or `make deploy-dns-watchdog` from the repo root.

## Environment variables

All of these are set with explicit defaults in `deployment.yaml`; override
with `kubectl -n kube-system set env deploy/dns-watchdog KEY=VALUE`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `PROBE_INTERVAL` | `30` | Seconds to sleep between probe rounds. |
| `PROBE_TIMEOUT` | `5` | Per-probe timeout in seconds (applies to every leg, including the API calls used for restart/Event). |
| `EXTERNAL_NAME` | `cloudflare.com` | Hostname resolved through cluster DNS for the primary probe and the upstream-bypass probe. |
| `INTERNAL_NAME` | `kubernetes.default.svc.cluster.local` | In-cluster service name resolved through CoreDNS for the internal-name leg. |
| `UPSTREAM_DNS` | `8.8.8.8` | DNS server queried directly (UDP/53), bypassing CoreDNS entirely, for the upstream-bypass leg. |
| `TCP_CONTROL_HOST` | `1.1.1.1` | Host used for the TCP control probe (no DNS involved -- an IP literal). |
| `TCP_CONTROL_PORT` | `443` | Port for the TCP control probe. |
| `FAILURE_THRESHOLD` | `3` | Consecutive primary-probe failures before an auto-restart is considered. |
| `AUTO_RESTART` | `false` | When `true`, restart CoreDNS once the threshold and cooldown both allow it. Off by default -- see *Why restart is off by default*. |
| `RESTART_COOLDOWN_SECONDS` | `1800` | Minimum seconds between restarts the watchdog performs itself. Prevents a restart loop if CoreDNS stays wedged. |

## Reading the structured failure line

On every primary-probe failure the watchdog emits one `key=value` log line
before deciding whether to restart, e.g.:

```text
timestamp=2026-09-19T03:14:07Z event=dns_probe_failed consecutive=2 cluster_dns=fail internal_name=fail upstream_udp=fail tcp_control=ok external_name=cloudflare.com upstream_dns=8.8.8.8
```

Four legs, each `ok` or `fail`:

| Leg | What it tests |
| --- | --- |
| `cluster_dns` | The primary probe: `nslookup $EXTERNAL_NAME` through cluster DNS (CoreDNS). |
| `internal_name` | `nslookup $INTERNAL_NAME`, still through CoreDNS -- an in-cluster name instead of an external one. |
| `upstream_udp` | `nslookup $EXTERNAL_NAME $UPSTREAM_DNS` -- direct UDP/53 to the upstream resolver, bypassing CoreDNS entirely. |
| `tcp_control` | TCP connect to `TCP_CONTROL_HOST:TCP_CONTROL_PORT` -- no DNS at all, an IP literal, so this isolates DNS from general pod-egress failure. |

Diagnosis from the combination (this is the point of running all four on
every failure, instead of reconstructing it afterwards):

| `cluster_dns` | `internal_name` | `upstream_udp` | `tcp_control` | Diagnosis |
| --- | --- | --- | --- | --- |
| fail | ok | ok | ok | CoreDNS is flaky/slow for this one name only, or a transient blip. |
| fail | fail | ok | ok | CoreDNS itself is wedged: it can't resolve anything, but a bypass to the upstream over UDP still works. Restart CoreDNS. |
| fail | fail | fail | ok | All DNS legs fail but the TCP control (no DNS involved) succeeds: pod-egress UDP/53 is broken while TCP/general egress is fine. This is what the 2026-09-19 incident looked like -- restarting CoreDNS "fixed" it, but the watchdog can't tell you why a CoreDNS restart un-wedges a node-level UDP path; that's still open (see the story's "Out of scope"). |
| fail | fail | fail | fail | Broader pod-egress or network outage, not DNS-specific. Look at CNI/node networking before touching CoreDNS. |

Recovery (a failure round immediately followed by a passing primary probe)
logs a matching structured line:

```text
timestamp=2026-09-19T03:15:37Z event=dns_probe_recovered consecutive_before=2 cluster_dns=ok external_name=cloudflare.com
```

## Auto-restart

When `consecutive >= FAILURE_THRESHOLD`, `AUTO_RESTART=true`, and at least
`RESTART_COOLDOWN_SECONDS` have passed since the watchdog's own last restart,
it patches the CoreDNS Deployment's pod template annotation the same way
`kubectl rollout restart deploy/coredns` does, logs
`event=dns_watchdog_restart`, and emits a `Normal` `CoreDNSRestarted` Event.
The consecutive-failure counter resets after a restart, and also on any
successful primary probe.

To disable auto-restart (observe/alert only):

```bash
kubectl -n kube-system set env deploy/dns-watchdog AUTO_RESTART=true
```

## Verifying it works

```bash
# Tail the structured log lines
kubectl -n kube-system logs deploy/dns-watchdog -f

# Confirm failure/recovery/restart Events are landing on the CoreDNS object
kubectl -n kube-system get events --field-selector involvedObject.name=coredns

# Static checks (RBAC scope, probe legs, env-var wiring) -- no cluster needed
make test-dns-watchdog
```

## Bootstrap trap

The watchdog only ever runs while cluster DNS may be broken, so it never
reaches the API server by hostname (never `kubernetes.default.svc` or any
other DNS name). It builds the API base URL from the kubelet-injected
`KUBERNETES_SERVICE_HOST` / `KUBERNETES_SERVICE_PORT` env vars (an IP and
port), authenticates with the projected ServiceAccount token, and verifies
TLS with the projected `ca.crt` -- see `watchdog.sh` in
`configmap-watchdog.yaml`.

## RBAC

`role-watchdog.yaml` grants the `dns-watchdog` ServiceAccount, scoped to `kube-system`
only (no ClusterRole/ClusterRoleBinding):

- `get` on `apps/deployments` (unscoped -- reading state isn't sensitive)
- `patch` on `apps/deployments`, restricted to `resourceNames: ["coredns"]`
  -- the only write verb granted anywhere in this file
- `create` on `""/events` -- no read/update/patch/delete

A compromised watchdog process can restart CoreDNS and emit Events. It
cannot touch any other Deployment, read Secrets, or exec into pods.

## Why restart is off by default

The incident this watchdog was built for (2026-09-19) looked like CoreDNS being
wedged: every external name failed, CoreDNS logged upstream timeouts, and a
restart appeared to fix it. None of that was the real fault.

A packet capture showed the upstream resolver accepting queries and never
answering, while the LAN resolver answered the identical query in under a
millisecond. Both were listed in the node's `/etc/resolv.conf`, CoreDNS forwards
to that file, and `forward`'s default policy is `random` -- so roughly half of
all lookups picked the dead upstream and stalled. Restarting CoreDNS changed
which coin flips happened next, nothing more.

An auto-restart would have fired repeatedly against a healthy CoreDNS, added
churn, and masked the signal that actually mattered: `upstream_udp=fail` next to
`tcp_control=ok` in the diagnostic line. Read that line first. Turn the restart
on only once you have a failure mode a restart demonstrably fixes.
