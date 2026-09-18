# KubeOpencode Sandbox Hardening

Strict-tier egress with minimal disruption to running agents.

## Why not block-all egress

Block-all breaks LLM providers, npm/pypi/github fetches, and `opencode` model
downloads. Strict tier allows public `443/53` but denies LAN by construction.

## What strict allows

* `kube-dns:53` UDP/TCP (CoreDNS pods **and** the kube-dns ClusterIP)
* Kubernetes API ClusterIP (`10.43.0.1:443` — verify per cluster via
  `kubectl get svc kubernetes -o jsonpath='{.spec.clusterIP}'`)
* Public `0.0.0.0/0:443,53` except `10/8,172.16/12,192.168/16,169.254/16,127/8`
* Implicit LAN deny: no `kubeopencode-server:2746` cross-talk, no other
  agents `:4096`, no cloud metadata `169.254.169.254`, no FritzBox LAN
  (`192.168.178.200:6443` leak seen in API discovery)
* `localhost` always allowed (Ollama `http://localhost:11434/v1` keeps working)
* server -> workspace `:4096` (control plane path only, `server-egress-strict`);
  agents still cannot reach each other on `:4096`

Native `NetworkPolicy` is allow-only, so deny is expressed via `except`.
For per-domain filtering (`openrouter.ai` only) migrate to Cilium
`toFQDNs` or an egress proxy later.

## LAN opt-in

Default `kubeopencode.io/allow-lan: ""` means no LAN. To allow e.g. LAN Ollama:

```yaml
metadata:
  annotations:
    kubeopencode.io/allow-lan: "ollama:11434"
```

Add a supplemental `NetworkPolicy` opening only that IP:port.

> **Operator-only boundary.** `allow-lan` is a meaningful gate only because the
> agent cannot set it itself: `k8s/kubeopencode/role-agent.yaml` (bound by
> `rolebinding-agent.yaml`) gives the agent SA (`kubeopencode-agent`) a least-privilege `Role` granting read-only pod
> access and no write on `networkpolicies`, `agents`, `secrets`, or
> `pods/patch`. If the agent SA were granted those, a compromised agent could
> patch its own annotation or create an allow-everything `NetworkPolicy` and
> bypass the whole strict tier. Verify with `kubectl auth can-i` (see *Verify*).

## API key: file, not ENV

`valueFrom.secretKeyRef` still leaks via `/proc/1/environ`, `env`, crash dumps.
Use:

1. `secret/opencode-api-key` (created imperatively, never committed to git)
   mounted `0400` at `/run/secrets/opencode/api-key`
2. Server reads `OPENCODE_API_KEY_FILE`, wrapper unsets `OPENCODE_API_KEY`
   after start and binds `--hostname 127.0.0.1`
3. Per-agent keys; rotate by re-running the imperative `create secret` below
   (the `kubeopencode.io/rotate: "true"` annotation marks rotation intent)
4. Enforce auth on `/api/session` (currently unauthenticated)

## Zero-downtime rollout

`NetworkPolicy` enforces on apply, no audit mode. Apply in order:

```bash
# Secret created imperatively (real value only in the operator's shell env,
# never in git -- same pattern as deployment/kubeopencode/README.md):
kubectl -n kubeopencode-system create secret generic opencode-api-key \
  --from-literal=api-key="$OPENCODE_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n kubeopencode-system label secret opencode-api-key --overwrite app.kubernetes.io/part-of=kubeopencode
kubectl -n kubeopencode-system annotate secret opencode-api-key --overwrite kubeopencode.io/rotate=true
kubectl apply -f role-agent.yaml -f rolebinding-agent.yaml
kubectl apply -f networkpolicy-egress-strict.yaml
kubectl apply -f networkpolicy-egress-server.yaml
kubectl apply -f networkpolicy-allow-server-ingress.yaml
# verify new agent: LLM OK, LAN blocked, /api/session -> 401, env clean
kubectl apply -f networkpolicy-default-deny.yaml
kubectl apply -f agent-desktop.yaml
```

Running agents drain via `standby.idleTimeout: 30m`. If a workload breaks,
add a temporary tier exception annotation, never remove default-deny.

### Label taxonomy

Two label sets share the namespace, and mixing them up is the single easiest way
to break this tier. Check yours with
`kubectl -n kubeopencode-system get pods --show-labels`:

| | platform (gateway, controller) | workspace (per agent) |
| --- | --- | --- |
| `app.kubernetes.io/name` | `kubeopencode` | `kubeopencode-server` |
| `app.kubernetes.io/instance` | `kubeopencode` | the agent name |
| `app.kubernetes.io/managed-by` | *absent* | `kubeopencode` |

So `name: kubeopencode-server` is a **workspace** pod, not the gateway. The
policies key on `managed-by` instead: present selects workspaces
(`agent-egress-strict`), absent selects the platform (`server-egress-strict`).
Every pod in the namespace therefore falls under exactly one egress policy, and a
new platform component cannot land with no egress at all. If your operator labels
pods differently, fix both `podSelector`s before relying on the tier --
`agent-egress-strict` selecting nothing is silently unenforced, and
`server-egress-strict` selecting nothing is a total outage for the gateway.

## Verify

```bash
make verify-kubeopencode-netpol      # or: bash scripts/verify-kubeopencode-netpol.sh
```

Exits non-zero if any guarantee below is broken, so it drops straight into a
pipeline stage that has a kubeconfig. It stands up three throwaway pods and one
Service, then deletes them (`KEEP_PROBES=1` to leave them for debugging).
`NAMESPACE`, `LAN_TARGET`, `PUBLIC_URL`, `CURL_IMAGE`, `LISTENER_IMAGE` and
`TIMEOUT` are env overrides.

It uses purpose-built probes rather than exec-ing into a live agent for two
reasons. Agents scale to zero on `standby.idleTimeout`, so a suite pinned to a
real agent fails with `error: timed out waiting for the condition` depending on
who used the cluster last. And the probes wear the two label sets *deliberately*
-- absent vs. present `managed-by` -- which is what the policies select on, so
the suite tests the policy rather than one pod's current labels.

| from | to | expected |
| --- | --- | --- |
| platform | workspace `:4096` | reachable |
| platform | kubernetes API | reachable |
| agent | kubernetes API | reachable |
| agent | public HTTPS | reachable |
| agent | LAN (`192.168.178.200:6443`) | blocked |
| agent | cloud metadata (`169.254.169.254`) | blocked |
| agent | another agent `:4096` | blocked |

Plus the RBAC half of the `allow-lan` trust boundary, impersonating the agent SA:
`list pods` yes; `patch pods`, `create networkpolicies`, `patch agents` and
`get secrets` no.

A blocked result is a connection that never completed (`curl` exit 7 or 28). The
script separates that from a name that did not resolve (exit 6) on purpose: a
broken-DNS regression must not be able to masquerade as a passing "blocked"
assertion, which is exactly how the outage above would have slipped through.

The selector invariants are also checked without a cluster, in CI:

```bash
make test-kubeopencode-netpol        # scripts/test_kubeopencode_netpol.py
```

### Manual spot checks

These run *inside* a pod, and the shell there is dash/busybox -- `/dev/tcp` is a
bash builtin and fails with "Directory nonexistent" whatever the policy does, so
use `curl` and read the exit code:

```bash
POD=$(kubectl -n kubeopencode-system get pod -l app.kubernetes.io/managed-by=kubeopencode \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n kubeopencode-system exec "$POD" -- sh -c 'env | grep -i key'          # empty
kubectl -n kubeopencode-system exec "$POD" -- \
  curl -s -o /dev/null -w '%{http_code}\n' localhost:4096/api/session            # 401
kubectl -n kubeopencode-system exec "$POD" -- \
  sh -c 'curl -sk -m 3 -o /dev/null -w "%{http_code}\n" https://192.168.178.200:6443/version; echo exit=$?'
                                                                                 # 000, exit=7 or 28
kubectl -n kubeopencode-system exec "$POD" -- \
  curl -s -o /dev/null -w '%{http_code}\n' https://openrouter.ai/api/v1/models    # 200
```

RBAC has to impersonate the agent service account. Without `--as=` these answer
for whoever runs them, which is normally a cluster admin -- every answer is yes
and the check is worthless:

```bash
SA=system:serviceaccount:kubeopencode-system:kubeopencode-agent
kubectl auth can-i list pods -n kubeopencode-system --as=$SA              # yes (role-agent.yaml grants it)
kubectl auth can-i patch pods -n kubeopencode-system --as=$SA             # no (no self-annotation)
kubectl auth can-i create networkpolicies -n kubeopencode-system --as=$SA # no (operator-only)
kubectl auth can-i patch agents.kubeopencode.io -n kubeopencode-system --as=$SA # no (no allow-lan self-escalation)
kubectl auth can-i get secrets -n kubeopencode-system --as=$SA            # no
```

## Troubleshooting

### `lookup <workspace>.kubeopencode-system.svc.cluster.local ... i/o timeout`

A dropped (not refused) DNS packet: egress to cluster DNS is denied. `default-deny-all`
uses `podSelector: {}`, so **every** pod in the namespace loses egress, and only the
pods a later policy re-allows get it back. Two ways this bites:

1. **The namespace selector matches nothing.** Cluster DNS must be selected via
   `kubernetes.io/metadata.name: kube-system`. The API server sets that label on
   every namespace; a bare `name: kube-system` label is not set by default on k3s
   or upstream k8s, so a rule keyed on it silently allows nothing. The public
   `0.0.0.0/0:53` rule does not cover the gap -- CoreDNS lives at `10.43.0.10`,
   inside the `except: 10.0.0.0/8` block.
2. **The pod is not an agent.** `agent-egress-strict` only selects
   `app.kubernetes.io/managed-by: kubeopencode`. The gateway and controller are
   caught by the deny and restored by `networkpolicy-egress-server.yaml` instead,
   which selects on `managed-by` being *absent*. Resolve the source IP to a pod
   first, then check its labels against *Label taxonomy* above -- a selector that
   names `kubeopencode-server` is matching workspaces, not the gateway.

Confirm before changing anything:

```bash
# Which pod is the source IP from the error?
kubectl get pods -A -o wide | grep <source-ip>
# Does anything select cluster DNS?
kubectl get ns kube-system --show-labels
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
# Are the policies selecting the pods you think they are?
kubectl -n kubeopencode-system get pods --show-labels
kubectl -n kubeopencode-system describe netpol
# Resolve from inside the affected pod
kubectl -n kubeopencode-system exec <pod> -- nslookup kubernetes.default
```

Once DNS resolves, the next hop is the connect itself: workspace pod IPs are in the
pod CIDR (`10.42.0.0/16` on k3s), which the strict `except: 10.0.0.0/8` denies. That
path is allowed by podSelector in `server-egress-strict`, not by ipBlock -- an
`ipBlock` peer can never reach it while the `except` stands.

### Rolling back

`kubectl -n kubeopencode-system delete netpol default-deny-all` restores egress for
every pod immediately. Do that to confirm a failure is policy-related, then
re-apply once the selectors are fixed -- never leave the deny off.
