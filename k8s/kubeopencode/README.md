# kubeopencode config

Kubernetes manifests and docs for running the `default-wf2` opencode agent on the
home k3s cluster (namespace `kubeopencode-system`), plus mobile access, the
custom-opencode-image workflow, and strict-tier sandbox hardening (NetworkPolicy
and least-privilege RBAC) — see [`docs/SECURITY-KUBEOPENCODE.md`](../../docs/SECURITY-KUBEOPENCODE.md).

> **No secrets are committed here.** The manifests reference Kubernetes Secrets by name;
> create those out-of-band (commands below). Never commit real tokens/passwords.

## Files

| File | What it is |
|---|---|
| `agent-default-wf2.yaml` | The `default-wf2` `Agent`, self-contained and **converging with the live object** (BITB-171/172): full config via `configRef` → the `opencode-config` ConfigMap, PVC-backed persistence (workspace 20Gi + sessions 2Gi, BITB-128), the three provider credentials, and the pinned custom `agentImage` + `ghcr-pull` pull secret. Over the live object it converges; standalone it needs the secrets, ConfigMap, and RBAC below. Kept in parity with `deployment/kubeopencode/agent.yaml` by `scripts/test_kubeopencode_manifests.py`. |
| `agent-default-wf3.yaml` | Second Agent (`default-wf3`) for testing the custom agent image — identical shape to `default-wf2` (configRef, persistence, credentials, image wiring) with its own PVCs; validated on the home cluster 2026-09-30 (BITB-172). |
| `service-mobile.yaml` | Stable Service both remote paths target (also carries Tailscale annotations). |
| `cloudflared-deployment.yaml` | In-cluster `cloudflared` connector (token mode) for the Cloudflare WARP + private-route path. |
| `mobile-access.md` | Plan/runbook for reaching the agent from the phone app (Cloudflare WARP + Tailscale). |
| `custom-opencode-image.md` | How to build/publish a custom agent image to run a newer opencode. |
| `dev-image/` | Derivative of `kubeopencode-agent-devbox` (the `executorImage`, not `agentImage`) adding `ripgrep`, `pytest`, `pre-commit`, `PyYAML`, and pre-warmed `pre-commit` hook envs on top of what that base already ships (`git`/`make`/`curl`/`jq`/`gh`/`kubectl`/`yq`/system Node 22.x/`python3`), so `make pre-commit`/`make verify-opencode-config` work in-pod (BITB-158). See `dev-image/README.md`. |
| `role-agent.yaml` | Least-privilege `Role` for the `kubeopencode-agent` ServiceAccount (read-only pod access; no write on NetworkPolicies/Agents/Secrets — the trust boundary that keeps `allow-lan` operator-only). |
| `rolebinding-agent.yaml` | Binds that Role to the SA; required before applying any Agent that sets `serviceAccountName: kubeopencode-agent`. |
| `agent-desktop.yaml` | `desktop` Agent **example sketch — UNVERIFIED against the live object** (only fragments of the live spec are known; the sketch sets no configRef/config, no credentials, and **no `agentImage` pin**, so live runs the unpinned `agent-opencode:latest` — binary-contract risk, BITB-283): strict-tier annotations, sessions persistence, standby scale-to-zero. Export the live spec, diff it against this sketch, and pin `agentImage` before any apply — owner steps in the [BITB-283 story](../../docs/BACKLOG_STORIES/BITB-283-agent-manifest-coverage-gap-wf3-desktop.md). |
| `networkpolicy-default-deny.yaml` | `default-deny-all` egress deny for every pod in the namespace. **Must be applied LAST** — see *Sandbox hardening*. |
| `networkpolicy-egress-strict.yaml` | `agent-egress-strict`: strict-tier egress for workspace pods (cluster DNS, K8s API, public 443/53; RFC1918/link-local/loopback denied by construction). |
| `networkpolicy-egress-server.yaml` | `server-egress-strict`: strict-tier egress for the platform pods (gateway/controller), selected by the absence of `app.kubernetes.io/managed-by`, plus the gateway→workspace `:4096` control-plane path. |
| `networkpolicy-allow-server-ingress.yaml` | `allow-server-ingress`: ingress to workspace `:4096` from the platform gateway and `kube-system` probes. |
| `ingress-server.yaml` | Optional traefik `Ingress` (`chat.home.local`) for LAN browser access to the platform gateway Service on `:2746`. |

## Secrets to create (not stored in git)

Each secret is wired into `agent-default-wf2.yaml` / `agent-default-wf3.yaml` via
`credentials[].secretRef` → the env var named in the comment (a missing secret
fails the pod with `CreateContainerConfigError` — the manifests' prerequisite
list is their header comment):

```bash
# provider key (OpenCode Zen) → OPENCODE_API_KEY
kubectl -n kubeopencode-system create secret generic ai-credentials \
  --from-literal=api-key='<opencode-zen-key>'

# opencode server Basic-auth password — OPTIONAL, mobile flow only (NOT pre-wired
# in the manifests; create it when enabling mobile access per mobile-access.md)
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

# GHCR pull secret — REQUIRED: the manifests pin the custom agent image
# (ghcr.io/zioalex/... — a private package) and reference this pull secret
# (custom-opencode-image.md Option B)
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
kubectl apply -f agent-default-wf3.yaml      # optional: custom-image test agent (BITB-172)
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
resilience, troubleshooting: [`deployment/kubeopencode/README.md`](../../deployment/kubeopencode/README.md)
(that folder is obsolete per the 2026-11-09 owner ruling — k8s/kubeopencode/ is the
canonical home and the runbook migrates here under BITB-285).

## What the controller owns (BITB-284)

The `kubeopencode-controller` renders each Agent's Deployment and Service
**from the Agent spec alone** and overwrites the whole object spec on
every reconcile (`existing.Spec = desired.Spec` —
[`agent_controller.go` `reconcileDeployment`](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/agent_controller.go#L269-L275),
upstream v0.1.9; no diff, no merge). **Anything hand-patched onto the
Deployment does not survive** — and the patch itself triggers the
reconcile that reverts it (the controller `Owns()` the Deployment, so a
`kubectl set image`/`kubectl patch` fires the watch → re-render →
overwrite, typically within seconds). Consequence: the only durable
control surface is the **Agent object** — express the change there or
expect reversion.

**Observed live (2026-11-09 outage):** a deployment-level `set image`
was wiped by a reconcile; controller restarts (40→41 that morning) and
Agent spec changes each re-rendered templates; the BITB-172 hand-wired
image survived only until the first re-render — which is why these
committed manifests exist (repo applies converge with live instead of
fighting it).

Reconcile triggers (upstream source, v0.1.9 commit `a54986b` — verified
identical on current `main`, 2026-11-09): any Agent change; any event on
**owned** objects (Deployment — including the Deployment controller's
own status writes during pod churn — Service, the controller-created
context ConfigMap, PVCs, share-token Secret); AgentTemplate changes;
Task lifecycle events; controller restart (informers re-list → every
agent re-rendered); and the controller-runtime default **~10h resync**
(no `SyncPeriod` override). An identical render is a no-op update —
reconciles only roll pods when the rendered template actually changed.

One important non-trigger: the **`configRef` ConfigMap is not watched**
— `opencode-config` is read at reconcile time and baked into the pod
template (serve command / context-init). That is why the sync flow above
requires the pod replacement: the `kubectl delete pod` churns the
Deployment status → reconcile → re-render with the *fresh* ConfigMap
content → changed template → rolling update. A ConfigMap-only change on
an otherwise quiet cluster does not converge until the ~10h resync.

Operational guidance:

- **Never hand-patch the Deployment for anything that must survive.**
  Effectively nothing in its `.spec` (nor object-level labels) is safe
  across reconciles. `spec.suspend` on the Agent is the one
  deployment-shaping field the controller deliberately honors (scales
  to 0).
- The legitimate exception: an **emergency** patch while the controller
  is *down* (crash-looping, as during the 2026-11-09 outage). Expect
  reversion when it recovers; follow up with the Agent-spec change.
- Spec-expressible today: `agentImage`, `executorImage`, `attachImage`,
  `imagePullSecrets`, `port`/`extraPorts`, credentials, contexts,
  skills, plugins, `configRef`, persistence, `serviceAccountName`,
  `suspend`, and `podSpec.*` (resources, securityContext, lifecycle,
  annotations, scheduling, extraEnv, extraVolumes/Mounts,
  systemContainers env/volumeMount overrides).
- **Probes are owned and not spec-expressible anywhere** — see the next
  subsection.
- Cluster-level `KubeOpenCodeConfig` adds no image/probe knobs for the
  server container: `systemImage`/`systemImagePullPolicy` cover only the
  internal init/sidecar containers (git-init, context-init, plugin-init,
  git-sync), plus proxy/clusterDomain/observability.

### Startup-probe budget — hardcoded upstream (BITB-282)

The `opencode-server` startup probe is hardcoded in the controller
([`server_builder.go` lines 593–605](https://github.com/kubeopencode/kubeopencode/blob/a54986bff8c25d974670953ca8ec4882e3964186/internal/controller/server_builder.go#L593-L605)):
`GET /session/status`, `initialDelaySeconds: 2`, `periodSeconds: 2`,
`timeoutSeconds: 5`, `failureThreshold: 30` — the upstream author's
comment sizes that at "2 + 2\*30 = 62s max startup time". The 2026-11-09
outage showed the real envelope is worse in both directions: fast
refusals kill at ~62s, but when the port is bound and the endpoint
hangs, each probe consumes the full 5s timeout, so 30 failures stretch
toward ~150s — the incident's kills landed at **~100–115s** (after ~65s
of `connection refused` + ~50s of `context deadline exceeded` while
opencode init/plugin/npm resolution crawled on a degraded ~2.2 MB/s
network). A cold boot that needs more than ~62–150s cannot boot on this
controller version, and because the reconcile owns the Deployment, a
deployment-level probe patch is reverted (see above) — there is **no
workaround**. Worst-case cold boots need ~300s. The Agent spec (checked
on v0.1.9 and on current upstream `main`, 2026-11-09: `AgentSpec`,
`podSpec`, `podSpec.systemContainers`, `AgentTemplate`,
`KubeOpenCodeConfig`) exposes no probe fields — an upstream issue asking
for spec-expressible probe overrides is drafted in the
[BITB-282 story](../../docs/BACKLOG_STORIES/BITB-282-startup-probe-budget-cold-boot-outage.md)
(filing is an owner step). Until upstream ships it, the mitigations
are: don't panic-roll images on probe-kill loops (the 2026-11-09 outage
self-healed once the network dip cleared; the image was verified fine),
keep pods warm (`persistence`, BITB-128), and use the rollback anchors
below only for verified image-content breakage.

## Known-good image digests (rollback anchors) (BITB-283)

| Image | Digest | Verified |
| --- | --- | --- |
| `ghcr.io/kubeopencode/kubeopencode-agent-devbox` | `sha256:1be2d086185e06572622d2ab87aa6eb93e6031c7c18953c0551869a39a617669` | 2026-11-09: healthy through the outage == the digest pulled during the outage == the then-current upstream `:latest` (GHCR API check) |

The 2026-11-09 outage was **not** an image-content problem — the exonerating
evidence is exactly this triple equality (an early "upstream broke
`:latest`" hypothesis was retracted; see the
[BITB-282 story](../../docs/BACKLOG_STORIES/BITB-282-startup-probe-budget-cold-boot-outage.md)).
This anchor exists so that if image content is *ever* the problem, the
one-command rollback is on record:

```bash
kubectl -n kubeopencode-system set image deployment/<agent>-server \
  opencode-server=ghcr.io/kubeopencode/kubeopencode-agent-devbox@sha256:1be2d086185e06572622d2ab87aa6eb93e6031c7c18953c0551869a39a617669
```

**Caveat (BITB-284):** that command patches the Deployment, which the
controller owns — a reconcile re-renders the template from the Agent
spec and **reverts the patch** (the patch itself triggers it). It buys
time only while the controller is down or between reconciles. The
durable form is the Agent-spec equivalent, which *survives* reconciles:

```bash
kubectl -n kubeopencode-system patch agent <agent> --type=merge \
  -p '{"spec":{"executorImage":"ghcr.io/kubeopencode/kubeopencode-agent-devbox@sha256:1be2d086185e06572622d2ab87aa6eb93e6031c7c18953c0551869a39a617669"}}'
```

…then remove the `executorImage` override once upstream `:latest` is
verified good again. (Note: `opencode-server` runs the devbox
`executorImage`; the opencode *binary* comes from the `opencode-init`
container's `agentImage` — pin that separately, per
[`custom-opencode-image.md`](custom-opencode-image.md). The
`default-wf2` / `default-wf3` manifests here pin `agentImage`;
`desktop` currently runs it **unpinned `:latest`** — see its
[Files](#files) entry and the
[BITB-283 story](../../docs/BACKLOG_STORIES/BITB-283-agent-manifest-coverage-gap-wf3-desktop.md).)

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
[`docs/SECURITY-KUBEOPENCODE.md`](../../docs/SECURITY-KUBEOPENCODE.md).

See `mobile-access.md` for the full mobile flow and `custom-opencode-image.md` for
updating opencode.
