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

> Verify the operator labels agent pods `app.kubernetes.io/managed-by:
> kubeopencode` (`kubectl get pods -l app.kubernetes.io/managed-by=kubeopencode
> -n kubeopencode-system`). If labels differ, `agent-egress-strict` selects
> nothing and is silently unenforced — update `podSelector` before relying on it.

## Verify

```bash
env | grep -i key # empty
curl -s localhost:4096/api/session # 401
timeout 3 bash -c "echo > /dev/tcp/192.168.178.200/6443" # fail
curl -s https://openrouter.ai/api/v1/models | head # OK
kubectl auth can-i list pods -n kubeopencode-system # no
kubectl auth can-i create networkpolicies -n kubeopencode-system # no (operator-only)
kubectl auth can-i patch agents -n kubeopencode-system # no (agent can't self-escalate allow-lan)
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
   `app.kubernetes.io/managed-by: kubeopencode`. The operator/server pod is caught
   by the deny and restored by `networkpolicy-egress-server.yaml` instead. If your
   server pod carries different labels, fix that policy's `podSelector` first.

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
