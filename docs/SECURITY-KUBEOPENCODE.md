# KubeOpencode Sandbox Hardening

Strict-tier egress with minimal disruption to running agents.

## Why not block-all egress

Block-all breaks LLM providers, npm/pypi/github fetches, and `opencode` model
downloads. Strict tier allows public `443/53` but denies LAN by construction.

## What strict allows

* `kube-dns:53` UDP/TCP
* Kubernetes API ClusterIP (`10.43.0.1:443` — verify per cluster via
  `kubectl get svc kubernetes -o jsonpath='{.spec.clusterIP}'`)
* Public `0.0.0.0/0:443,53` except `10/8,172.16/12,192.168/16,169.254/16,127/8`
* Implicit LAN deny: no `kubeopencode-server:2746` cross-talk, no other
  agents `:4096`, no cloud metadata `169.254.169.254`, no FritzBox LAN
  (`192.168.178.200:6443` leak seen in API discovery)
* `localhost` always allowed (Ollama `http://localhost:11434/v1` keeps working)

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

## API key: file, not ENV

`valueFrom.secretKeyRef` still leaks via `/proc/1/environ`, `env`, crash dumps.
Use:

1. `secret/opencode-api-key` mounted `0400` at `/run/secrets/opencode/api-key`
2. Server reads `OPENCODE_API_KEY_FILE`, wrapper unsets `OPENCODE_API_KEY`
   after start and binds `--hostname 127.0.0.1`
3. Per-agent keys, rotate via annotation `kubeopencode.io/rotate: "true"`
4. Enforce auth on `/api/session` (currently unauthenticated)

## Zero-downtime rollout

`NetworkPolicy` enforces on apply, no audit mode. Apply in order:

```bash
kubectl apply -f secret-opencode-api-key.yaml
kubectl apply -f networkpolicy-egress-strict.yaml
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
```
