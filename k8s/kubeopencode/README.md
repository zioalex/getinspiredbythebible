# kubeopencode config

Kubernetes manifests and docs for running the `default-wf2` opencode agent on the
home k3s cluster (namespace `kubeopencode-system`), plus mobile access, the
custom-opencode-image workflow, and strict-tier sandbox hardening (NetworkPolicy
and least-privilege RBAC) — see [`docs/SECURITY-KUBEOPENCODE.md`](../SECURITY-KUBEOPENCODE.md).

> **No secrets are committed here.** The manifests reference Kubernetes Secrets by name;
> create those out-of-band (commands below). Never commit real tokens/passwords.

## Files

| File | What it is |
|---|---|
| `agent-default-wf2.yaml` | The `default-wf2` `Agent`, self-contained (BITB-171): full config via `configRef` → the `opencode-config` ConfigMap, PVC-backed persistence (workspace 20Gi + sessions 2Gi, BITB-128), all provider credentials, plus `OPENCODE_SERVER_PASSWORD` for mobile Basic auth; safe to apply standalone or over the live object (kept in parity with `deployment/kubeopencode/agent.yaml` by `scripts/test_kubeopencode_manifests.py`). Set `agentImage` here to pin the opencode version. |
| `service-mobile.yaml` | Stable Service both remote paths target (also carries Tailscale annotations). |
| `cloudflared-deployment.yaml` | In-cluster `cloudflared` connector (token mode) for the Cloudflare WARP + private-route path. |
| `mobile-access.md` | Plan/runbook for reaching the agent from the phone app (Cloudflare WARP + Tailscale). |
| `custom-opencode-image.md` | How to build/publish a custom agent image to run a newer opencode. |
| `dev-image/` | Derivative of `kubeopencode-agent-devbox` (the `executorImage`, not `agentImage`) adding `ripgrep`, `pytest`, `pre-commit`, `PyYAML`, and pre-warmed `pre-commit` hook envs on top of what that base already ships (`git`/`make`/`curl`/`jq`/`gh`/`kubectl`/`yq`/system Node 22.x/`python3`), so `make pre-commit`/`make verify-opencode-config` work in-pod (BITB-158). See `dev-image/README.md`. |
| `role-agent.yaml` | Least-privilege `Role` for the `kubeopencode-agent` ServiceAccount (read-only pod access; no write on NetworkPolicies/Agents/Secrets — the trust boundary that keeps `allow-lan` operator-only). |
| `rolebinding-agent.yaml` | Binds that Role to the SA; required before applying any Agent that sets `serviceAccountName: kubeopencode-agent`. |
| `agent-desktop.yaml` | Example `desktop` Agent with strict-tier annotations, persistence, and standby scale-to-zero. |
| `networkpolicy-default-deny.yaml` | `default-deny-all` egress deny for every pod in the namespace. **Must be applied LAST** — see *Sandbox hardening*. |
| `networkpolicy-egress-strict.yaml` | `agent-egress-strict`: strict-tier egress for workspace pods (cluster DNS, K8s API, public 443/53; RFC1918/link-local/loopback denied by construction). |
| `networkpolicy-egress-server.yaml` | `server-egress-strict`: strict-tier egress for the platform pods (gateway/controller), selected by the absence of `app.kubernetes.io/managed-by`, plus the gateway→workspace `:4096` control-plane path. |
| `networkpolicy-allow-server-ingress.yaml` | `allow-server-ingress`: ingress to workspace `:4096` from the platform gateway and `kube-system` probes. |
| `ingress-server.yaml` | Optional traefik `Ingress` (`chat.home.local`) for LAN browser access to the platform gateway Service on `:2746`. |

## Secrets to create (not stored in git)

Each secret is wired into `agent-default-wf2.yaml` via `credentials[].secretRef` →
the env var named in the comment:

```bash
# provider key (OpenCode Zen) → OPENCODE_API_KEY
kubectl -n kubeopencode-system create secret generic ai-credentials \
  --from-literal=api-key='<opencode-zen-key>'

# opencode server Basic-auth password (mobile app) → OPENCODE_SERVER_PASSWORD
kubectl -n kubeopencode-system create secret generic opencode-server-auth \
  --from-literal=password="$(openssl rand -hex 20)"

# cloudflared tunnel token (Cloudflare path only)
kubectl -n kubeopencode-system create secret generic cloudflared-token \
  --from-literal=token='<tunnel-token>'

# OpenRouter key → OPENROUTER_API_KEY — paid primary for android-gemini + tier-2
# runtime fallback for every agent (cross-provider resilience; see
# deployment/kubeopencode/README.md)
kubectl -n kubeopencode-system create secret generic openrouter-api-key \
  --from-literal=openrouter-api-key='<openrouter-key>'

# GitHub Copilot OAuth token → GITHUB_TOKEN (gho_... — PATs of every kind are
# rejected by the token exchange; see deployment/kubeopencode/README.md
# "Persist GitHub Copilot access")
kubectl -n kubeopencode-system create secret generic github-copilot-auth \
  --from-literal=token="$(gh auth token)" # pragma: allowlist secret

# GHCR pull secret (only if the custom agent image is private)
kubectl -n kubeopencode-system create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io --docker-username=<user> \
  --docker-password='<PAT read:packages>' --docker-email=<email>

# opencode API key — hardening path only (file-mounted, read via OPENCODE_API_KEY_FILE).
# The default-wf2 manifest uses the `ai-credentials` env route instead, so this secret
# is only needed for hardened agents (see docs/SECURITY-KUBEOPENCODE.md).
kubectl -n kubeopencode-system create secret generic opencode-api-key \
  --from-literal=api-key="$OPENCODE_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n kubeopencode-system label secret opencode-api-key --overwrite app.kubernetes.io/part-of=kubeopencode
kubectl -n kubeopencode-system annotate secret opencode-api-key --overwrite kubeopencode.io/rotate=true
```

## Apply order

```bash
# 1. secrets (above)
# 2. RBAC (required by every Agent manifest that sets serviceAccountName: kubeopencode-agent)
kubectl apply -f role-agent.yaml -f rolebinding-agent.yaml
# 3. agent + service (the opencode-config ConfigMap must exist first — see "OpenCode config")
kubectl apply -f agent-default-wf2.yaml
kubectl apply -f service-mobile.yaml      # paste the live selector first — see file header
# 4. mobile remote access (pick Cloudflare and/or Tailscale) — see mobile-access.md
kubectl apply -f cloudflared-deployment.yaml
```

## OpenCode config (agent definitions → ConfigMap)

Agent behaviour (the 12-agent orchestrator/subagent roster, models,
`fallback_models`, permissions) is **not** inline in the manifests in this
directory. Source of truth: `.opencode/agents/*.md`, compiled into the
committed `opencode.json`, which reaches the cluster as the `opencode-config`
ConfigMap (key `opencode.json`) in `kubeopencode-system`.

From the **repo root**:

```bash
make gen-opencode-config        # regenerate opencode.json after editing .opencode/agents/*.md (commit the result)
make verify-opencode-config     # validate: JSON, all 12 agents, every agent has fallback_models, fallback plugin configured
make sync-opencode-configmap    # runs the verify chain, then creates/updates the ConfigMap in kubeopencode-system
```

> **ConfigMap before configRef Agents.** An Agent that consumes the full config
> via `spec.configRef` (like `deployment/kubeopencode/agent.yaml`) will not start
> unless the ConfigMap already exists — run `make sync-opencode-configmap`
> before applying such an Agent.

**Config changes need a pod restart.** Updating a ConfigMap does not restart
anything that already mounted it; running agents keep serving the previous
config until their pod is replaced:

```bash
kubectl -n kubeopencode-system get pods
kubectl -n kubeopencode-system delete pod <agent-pod>
```

`spec.configRef` (full 12-agent config from the ConfigMap) and inline
`spec.config` (bare `model`/`small_model` overrides) are
**mutually exclusive** (runtime-validated). A new agent that should use the
repo's full agent roster and fallbacks must use `configRef` — an inline
`spec.config` block yields only the bare model settings. Both `default-wf2`
manifests in this repo use `configRef`; `agent-desktop.yaml` sets neither and
runs on defaults.

Full runbook — secrets (OpenRouter, GitHub Copilot), persistence, cross-provider
resilience, troubleshooting: [`deployment/kubeopencode/README.md`](../../deployment/kubeopencode/README.md).

## Sandbox hardening (strict-tier egress)

Strict tier enforces public `443/53` + cluster DNS + K8s API only; LAN/metadata/loopback-range
IPs are denied by construction; agents cannot reach each other.

```bash
# 1. allow-policies first (egress allow + ingress allow)
kubectl apply -f networkpolicy-egress-strict.yaml
kubectl apply -f networkpolicy-egress-server.yaml
kubectl apply -f networkpolicy-allow-server-ingress.yaml
# verify new agent: LLM OK, LAN blocked, /api/session -> 401, env clean
# 2. default-deny LAST — it selects every pod in the namespace and enforces on apply
kubectl apply -f networkpolicy-default-deny.yaml
kubectl apply -f agent-desktop.yaml
```

> **⚠️ Warning:** `default-deny-all` uses `podSelector: {}` and enforces immediately.
> Applying it before the three allow-policies kills DNS/egress for the gateway too —
> that is why the order exists.

### Verification

```bash
make verify-kubeopencode-netpol      # live cluster
make test-kubeopencode-netpol        # static, runs in CI
```

### Rollback

```bash
kubectl -n kubeopencode-system delete netpol default-deny-all   # restores egress immediately
```

Full rationale, label taxonomy, LAN opt-in via `kubeopencode.io/allow-lan`, and troubleshooting:
[`docs/SECURITY-KUBEOPENCODE.md`](../SECURITY-KUBEOPENCODE.md).

See `mobile-access.md` for the full mobile flow and `custom-opencode-image.md` for
updating opencode.
