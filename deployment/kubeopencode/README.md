# KubeOpenCode Deployment Config

Adhoc folder for the KubeOpenCode `Agent` manifest. Agent behaviour, models,
and fallbacks live in `.opencode/agents/*.md` and are compiled into
`opencode.json` by `make gen-opencode-config`; this folder holds only the
cluster-side wiring (the `configRef` pointer and credentials).

## Prerequisites

- KubeOpenCode v0.1.8+ installed (supports `configRef` / inline `config`)
- Namespace `kubeopencode-system` exists
- ConfigMap `opencode-config` (key `opencode.json`) in `kubeopencode-system`
  — referenced by `spec.configRef`; the Agent will not start without it
- Secret `ai-credentials` with key `api-key` in `kubeopencode-system`
  → injected as `OPENCODE_API_KEY`
- Secret `openrouter-api-key` with key `openrouter-api-key` in
  `kubeopencode-system` → injected as `OPENROUTER_API_KEY` (required: every
  agent chain — primaries and fallbacks alike — is OpenRouter-only since
  BITB-279, so this key is the graph's single provider dependency; see
  [Fallback Resilience](#fallback-resilience))
- Secret `github-copilot-auth` in `kubeopencode-system` → Copilot credential
  for the `github-copilot/*` models (wired but unused since the 2026-09-14
  credit exhaustion — see the historical note in agents.md).
  Working mechanism today is key `token` (a `gho_…` OAuth user token) →
  injected as `GITHUB_TOKEN` (see `credentials` in agent.yaml). Key
  `auth.json` (an `opencode auth login` export) is the preferred long-lived
  mechanism, pending Agent-CRD file-mount support — see
  [Persist GitHub Copilot access](#persist-github-copilot-access).

### Create the secret

```bash
# Ensure namespace exists
kubectl create namespace kubeopencode-system --dry-run=client -o yaml | kubectl apply -f -

# OpenCode API key (replace with a real key)
kubectl -n kubeopencode-system create secret generic ai-credentials \
  --from-literal=api-key="YOUR_OPENCODE_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# OpenRouter key lives in its own secret (see `credentials` in agent.yaml)
kubectl -n kubeopencode-system create secret generic openrouter-api-key \
  --from-literal=openrouter-api-key="YOUR_OPENROUTER_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# GitHub Copilot OAuth token (gho_... — see "Persist GitHub Copilot access";
# PATs of any kind are rejected by the token exchange)
kubectl -n kubeopencode-system create secret generic github-copilot-auth \
  --from-literal=token="YOUR_GHO_OAUTH_TOKEN" \ # pragma: allowlist secret
  --dry-run=client -o yaml | kubectl apply -f -
```

### Create the ConfigMap

`agent.yaml` carries no inline config: it points at the `opencode-config`
ConfigMap via `spec.configRef`. That ConfigMap holds the generated
`opencode.json` (models, `fallback_models`, prompts, permissions, plugin,
provider timeouts). **Create it before applying the Agent** — otherwise the
Agent references a ConfigMap that does not exist and will not start.

From the repository root:

```bash
# Regenerate opencode.json from .opencode/agents/*.md, verify it, fast-forward
# the pod's shared checkout (+ in-pod plugin pre-flight tests), and
# create/update the ConfigMap in one step.
make sync-opencode-configmap
```

**Merge the PR before syncing.** The generated config loads the
task-reliability plugin via an absolute
`file:///workspace/repo/.opencode/plugin/task-reliability.ts` entry — a path
into the pod's shared git checkout. That checkout is fast-forwarded to
`origin/main` by the same target (`scripts/sync-opencode-workspace.sh`), so
config and plugin code stay in lockstep; a pre-merge sync would pair new
config with old plugin code — the exact cause of the 2026-11-08 live
`failed to load plugin … error="Plugin export is not a function"` incident
(BITB-269). The workspace update is fast-forward only: a diverged, dirty, or
detached checkout fails loudly instead of being rewritten, and the agents'
attached worktrees under `${WORKSPACE_DIR}/worktrees` are never touched.

The target runs, in order:

1. `verify-opencode-config` — a config missing agents, `fallback_models`,
   or the fallback plugin fails before it can reach the cluster.
2. `scripts/sync-opencode-workspace.sh` — `kubectl exec`s into the agent pod:
   `git fetch origin && git merge --ff-only origin/main` in `/workspace/repo`,
   then runs the plugin's unit tests (`node --experimental-strip-types
   --test .opencode/plugin/task-reliability.test.ts`) **in the pod**. Those
   tests enforce the opencode 1.18.31 plugin-loader contract (the plugin
   module must export exactly one default function; helpers live in
   `task-reliability-helpers.ts`) — the pre-live check that was missing when
   the 2026-11-08 "verified" plugin turned out to be rejected by the real
   loader.
3. The ConfigMap update (raw command below, if you are not using the
   Makefile).

This requires the runner's kubeconfig to allow `get`/`list` on pods and
`create` on `pods/exec` in `kubeopencode-system` (in addition to the
ConfigMap write), plus `git` and Node 22+ inside the agent pod (shipped by
the devbox executor image).

```bash
make gen-opencode-config   # writes ./opencode.json
kubectl -n kubeopencode-system create configmap opencode-config \
 --from-file=opencode.json=opencode.json \
 --dry-run=client -o yaml | kubectl apply -f -
```

Re-run `make sync-opencode-configmap` after any change to
`.opencode/agents/*.md`. Updating a ConfigMap does not restart anything that
already mounted it, so the running agent keeps serving the previous config
until its pod is replaced:

```bash
kubectl -n kubeopencode-system get pods          # find the agent pod
kubectl -n kubeopencode-system delete pod <agent-pod>
```

Verify what the cluster actually has:

```bash
kubectl -n kubeopencode-system get configmap opencode-config \
 -o jsonpath='{.data.opencode\.json}' | python3 -m json.tool | head -30
```

### After the pod restart: verify the plugin actually loaded

The 2026-11-08 incident was found this way — check the runtime log inside
the pod (`grep -a "failed to load plugin" /tmp/.local/share/opencode/log/opencode.log`)
and confirm it has **no** `task-reliability` entry after the restart
timestamp. Then dispatch any subagent task and confirm the durable registry
is being written:

```bash
kubectl -n kubeopencode-system exec <agent-pod> -- \
 sh -c 'grep -a "failed to load plugin" /tmp/.local/share/opencode/log/opencode.log | tail -3; \
        test -f /workspace/.opencode/task-registry.jsonl && \
        echo "registry OK:" && tail -3 /workspace/.opencode/task-registry.jsonl'
```

Expected: no new `failed to load plugin` lines, and after the first
subagent dispatch a JSONL line like
`{"kind":"created","childID":"ses_…","parentID":"ses_…","agent":"…","title":"…"}`.

## Pre-merge checklist for opencode config changes (BITB-280)

Any PR touching `opencode.json`, `.opencode/**`, or the config generator
must prove the change works in a REAL opencode runtime before it merges —
green unit tests are not enough (the 2026-11-08 18:51 incident: a plugin
with 26 green unit tests was dead on arrival in the live loader with
`Plugin export is not a function`).

1. **Run the live-config gate** (boots a scratch opencode pinned to the pod's
   version on the COMMITTED `opencode.json`, isolated HOME/XDG — never the
   live server):

   ```bash
   make test-opencode-config-live           # normal mode
   make test-opencode-config-live-selftest  # must catch the injected 18:51 bug
   ```

   The `opencode Live Config Gate` CI job runs both modes automatically on
   every `.opencode/**`/`opencode.json`/generator/Makefile change — but run
   them locally first; a scratch boot takes seconds and the failure output
   is richer than the CI log excerpt.
2. **Zero `failed to load plugin` for every config-listed `file://` plugin**
   is a hard requirement. npm-plugin resolution failures in the scratch env
   are warnings (infra flakiness), and failures from outside the tree under
   test are attributed to the pod's `/tools/opencode.json` leak — the gate
   classifies all of these for you.
3. **Pinned version discipline**: the gate pins the opencode version
   (`PINNED_OPENCODE_VERSION` in `scripts/test-opencode-config-live.py`) and
   cross-checks the `oc<x.y.z>` suffix of `agentImage` in `agent.yaml`. When
   the pod's opencode is upgraded, bump the image tag AND the constant in
   the same change or the gate blocks the merge — by design: the gate must
   test exactly what the pod runs.
4. **No provider key locally?** The dispatch-level check skips loudly
   ("dispatch-level validation deferred to pod pre-flight"); everything
   else still runs. In-pod runs have the key and exercise the full
   parent→child dispatch.
5. **Free-tier tier-1 invariant (BITB-279)**: every fallback chain's
   tier-1 hop must stay a free `openrouter/…:free` model — free models
   draw no credit, so the chain keeps serving while the paid key is
   exhausted (OpenRouter is the only credentialed provider; a paid tier-1
   would die with the same key, as the 2026-11-08 21:30 outage showed).
   The generator suite (`scripts/test_generate_opencode_config.py`)
   asserts this — keep it green on every model change.
6. After merge, the sync flow applies: `make sync-opencode-configmap`
   (which also fast-forwards the pod's shared checkout in lockstep and
   runs the in-pod plugin pre-flight tests), then replace the pod and
   verify the plugin actually loaded (see the section above).

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
image survived only until the first re-render — which is why `agent.yaml`
exists at all (repo applies converge with live instead of fighting it).

Reconcile triggers (upstream source, v0.1.9 commit `a54986b` — verified
identical on current `main`, 2026-11-09): any Agent change; any event on
**owned** objects (Deployment — including the Deployment controller's
own status writes during pod churn — Service, the controller-created
context ConfigMap, PVCs, share-token Secret); AgentTemplate changes;
Task lifecycle events; controller restart (informers re-list → every
agent re-rendered); and the controller-runtime default **~10h resync**
(no `SyncPeriod` override). An identical render is a no-op update —
reconciles only roll pods when the rendered template actually changed.

One deliberate non-trigger: the **`configRef` ConfigMap is not watched**
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
`k8s/kubeopencode/custom-opencode-image.md`. `default-wf2` and
`default-wf3` pin `agentImage` in their manifests; `desktop` currently
runs it **unpinned `:latest`** — see the `desktop` gap in
[the Files section](#files) and the
[BITB-283 story](../../docs/BACKLOG_STORIES/BITB-283-agent-manifest-coverage-gap-wf3-desktop.md).)

## Apply

Apply the Agent **after** the namespace, secrets, and ConfigMap above exist:

```bash
kubectl apply -f deployment/kubeopencode/agent.yaml        # default-wf2
kubectl apply -f deployment/kubeopencode/agent-wf3.yaml   # default-wf3 (added BITB-283 from the verified live spec)
kubectl -n kubeopencode-system get agent default-wf2 default-wf3
```

> **First `agent-wf3.yaml` apply — owner step (BITB-283):** the manifest
> is a faithful 2026-11-09 export of the live object, so the first apply
> must be a provable no-op:
> `kubectl -n kubeopencode-system diff -f deployment/kubeopencode/agent-wf3.yaml`
> (expect no diff) **before** applying.

The `desktop` agent has **no manifest in this folder, and its only repo
presence is an unverified example sketch** — `k8s/kubeopencode/agent-desktop.yaml`
(the k8s README calls it an "Example" agent: strict-tier annotations,
sessions-only persistence, 30m standby, **no configRef/config, no
credentials, no `agentImage` pin**). Nothing confirms that sketch matches
the live object (only fragments of the live spec are known), and applying
it as-is would be destructive — a `kubectl apply` of a manifest missing
fields that exist live removes them (the exact BITB-171 regression). Do
**not** apply or extend it from memory: export the live spec, diff it
against the sketch, pin `agentImage`, and promote a verified copy here —
the exact owner steps are in the
[BITB-283 story](../../docs/BACKLOG_STORIES/BITB-283-agent-manifest-coverage-gap-wf3-desktop.md).

If the Agent stays unready, check that the ConfigMap it references is present:

```bash
kubectl -n kubeopencode-system get configmap opencode-config
kubectl -n kubeopencode-system describe agent default-wf2
```

Also remember the startup-probe budget while waiting on a cold boot: on
this controller version a first boot that exceeds ~62s (fast refusals)
to ~150s (hanging probes) is killed and retried — slow pulls on a
degraded network make that loop visible before it recovers (see
*What the controller owns* → *Startup-probe budget*, BITB-282).

## Persist GitHub Copilot access

`/connect` stores OAuth in `~/.local/share/opencode/auth.json` (ephemeral,
lost on pod restart). `persistence.sessions/workspace` preserves DB/files,
not auth. Supply the credential declaratively so it survives restarts.

Requirements: a paid Copilot subscription (Pro, Pro+, Business, or
Enterprise) with [Copilot chat in the IDE](https://github.com/settings/copilot)
enabled. OpenCode exchanges the credential for a short-lived Copilot bearer
token via `https://api.github.com/copilot_internal/v2/token` and refreshes it
automatically.

### Personal access tokens do NOT work

`copilot_internal/v2/token` accepts **only OAuth user tokens** issued to a
Copilot-approved OAuth/GitHub App (`gho_…` / `ghu_…`). It rejects personal
access tokens of **every** kind — classic (`ghp_…`) *and* fine-grained
(`github_pat_…`) — with:

```text
Bad Request: checking third-party user token: bad request: Personal Access Tokens are not supported for this endpoint
```

The fine-grained **Copilot Requests** permission does not help: it governs the
*public* Copilot REST API (`/copilot/...` model endpoints), not the internal
IDE-token exchange OpenCode uses. Do not spend time hunting for that
permission — use one of the two options below.

### Option A — mount `auth.json` (preferred, self-refreshing)

Run `opencode auth login` → *GitHub Copilot* once on an interactive machine.
This writes a long-lived **refresh** token to
`~/.local/share/opencode/auth.json`, from which OpenCode re-mints the bearer
token indefinitely — nothing expires on a PAT/OAuth rotation schedule.

```bash
kubectl -n kubeopencode-system create secret generic github-copilot-auth \
  --from-file=auth.json="$HOME/.local/share/opencode/auth.json" \
  --dry-run=client -o yaml | kubectl apply -f -
```

The secret must then be mounted read-only at the agent's OpenCode data dir
(`$HOME/.local/share/opencode/auth.json` inside the pod). No manifest in
this repo pins the agent's runtime user or `$HOME`, so confirm the effective
user first (e.g. `kubectl -n kubeopencode-system exec <agent-pod> -- sh -c
'echo $HOME; id -u'`) rather than assuming `/root/...`. If the CRD gains a
`persistence` data-volume option, carrying that path on the existing data
volume is an equivalent alternative to a dedicated secret mount.

> **Not wirable today.** The `kubeopencode.io/v1alpha1` `Agent` CRD exposes
> only `credentials[].secretRef` → `env`; it has no `volumes`/`volumeMounts`
> (nor a persistence path covering the data dir). Until the CRD gains a
> file-mount field, use Option B.

### Option B — reuse an OAuth user token (works today)

The GitHub CLI's OAuth app is Copilot-approved, so its token is accepted:

```bash
gh auth login     # once, interactively
gh auth token     # prints gho_...
```

```bash
kubectl -n kubeopencode-system create secret generic github-copilot-auth \
  --from-literal=token="$(gh auth token)" \ # pragma: allowlist secret
  --dry-run=client -o yaml | kubectl apply -f -
```

`agent.yaml` already wires this:

```yaml
credentials:
  - name: github-copilot
    secretRef:
      name: github-copilot-auth
      key: token
    env: GITHUB_TOKEN
```

Caveats: the token is tied to your `gh` CLI session, is revoked by
`gh auth logout` or token rotation, and requires the subscription to stay
active. Rotate the secret when it changes.

### Troubleshooting

- `Personal Access Tokens are not supported for this endpoint` — the secret
  holds a `ghp_…`/`github_pat_…` PAT. Replace it with a `gho_…` token
  (Option B).
- `401`/`403` from the exchange — Copilot subscription inactive, or
  [Copilot chat in the IDE](https://github.com/settings/copilot) disabled.
- `403` on org repos / SSO wall — authorize the OAuth app for the SAML SSO
  organization (GitHub → Settings → Applications → Authorized OAuth Apps →
  SSO → Grant), then re-create the secret.
- Copilot models suddenly `401` — the `gho_…` token was revoked or rotated;
  re-run `gh auth token`, re-apply the secret, then delete the agent pod so it
  picks up the new value.

Verify the wiring:

```bash
# secret exists and Agent references it
kubectl -n kubeopencode-system get secret github-copilot-auth
kubectl -n kubeopencode-system describe agent default-wf2
```

## Fallback resilience

Every agent uses a **2-hop fallback chain** (free first, paid last, BITB-173)
that ends on OpenRouter. The `opencode-runtime-fallback@0.2.4` plugin retries on
`[400, 401, 402, 403, 429, 500, 502, 503, 504]` (auth/quota 4xx included, so a
provider returning "subscription exhausted" still fails over) with
`max_fallback_attempts: 2`:

```text
Primary model ──429/5xx──▶ Tier 1 fallback ──429/5xx──▶ Tier 2 fallback
```

The tier-1 hop is always a free `openrouter/:free` model — free models draw
no credit, so the chain keeps serving while the paid key is exhausted
(BITB-279; cross-provider hops are impossible: OpenRouter is the only
credentialed provider and the only free slate):

| Agent group | Primary | Tier 1 (free) | Tier 2 (paid) | Covers |
|---|---|---|---|---|
| Global builtins + orchestrator + 5 workhorse agents | `openrouter/z-ai/glm-5.3` (paid) | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/deepseek/deepseek-v3.2-exp` | Paid-key exhaustion → free tier-1 serves at zero credit |
| 4 skeptic agents (verifier / risk-auditor / failure-forecaster / seo-auditor) | `openrouter/deepseek/deepseek-v3.2-exp` (paid) | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/z-ai/glm-5.3` | Free-tier rate caps / upstream 5xx → paid tier-2 rescues |
| 2 mechanical agents (i18n-qa, verse-parity-keeper) | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/nvidia/nemotron-3.5-lightning:free` | `openrouter/z-ai/glm-5.3` | Free primary by design (BITB-236); de-duplicated tier-1 |

An OpenRouter gateway outage takes the whole graph down — the accepted
single-provider trade-off (no other credentialed provider exists; revisit if
one is ever added). `OPENROUTER_API_KEY` is the single point of provider
dependency. The per-agent table and rationale live in
[`agents.md`](agents.md), the source of truth; the `.opencode/agents/*.md`
frontmatter compiled into `opencode.json` is what actually ships.

> **Note (2026-09-14, historical):** `github-copilot/claude-opus-5` was the
> primary for orchestrator, verifier, and risk-auditor until Copilot
> subscription credits were exhausted; those agents moved to
> `opencode/nemotron-3-ultra-free` at the time (itself since retired by
> BITB-279 — the Zen gateway turned out to have no pod credentials).
> GitHub Copilot remains wired in `agent.yaml` and can be re-enabled as a
> primary (or as a third fallback hop) when access returns.

## Persistence (BITB-128)

`spec.persistence` in `agent.yaml` backs the agent with operator-managed PVCs.
Without it the workspace is an `EmptyDir`, so the `kubectl delete pod` step above
— which this runbook *requires* after every config sync — destroys the clone, any
uncommitted work, and the conversation history. (It preserves files and the
session DB — not Copilot auth, which is covered in the section above.)

```yaml
persistence:
  workspace: # spec.workspaceDir (/workspace): clone, branches, in-progress work
    size: 20Gi
  sessions: # OpenCode session SQLite DB: conversation history
    size: 2Gi
```

- The **operator creates and owns** these PVCs — there is no `pvc.yaml` to apply,
  and no `volumeMounts`/`fsGroup` to configure.
- `storageClassName` is intentionally omitted so the cluster default applies.
  Pin it per volume only if the default is unsuitable.
- **`/tmp` is not persisted.** Only `spec.workspaceDir` is. Place git worktrees
  under `${WORKSPACE_DIR}/worktrees` (see `AGENTS.md` → *Git Worktree Pattern*);
  `worktrees/` is gitignored because the repo is checked out at `$WORKSPACE_DIR`.
- Access mode is chosen by the operator. Verify it supports multi-attach before
  scaling the agent past one replica.

> **In-pod toolchain (BITB-158).** The base `executorImage`
> (`kubeopencode-agent-devbox`) ships most of the dev toolchain already
> (`git`/`make`/`curl`/`jq`/`gh`/`kubectl`/`yq`/system Node 22.x/`python3`)
> but not `ripgrep`/`pytest`/`pre-commit` -- every fresh pod repeated the same
> cold-install failures (`python3 -m pytest` with no `pytest` installed,
> `make pre-commit` unable to build a venv, hook caches wiped by the mandatory
> `kubectl delete pod` above). A derivative image that adds the missing
> pieces and bakes a pre-warmed `pre-commit` hook cache directly into the
> image layer (`PRE_COMMIT_HOME=/opt/pre-commit-seed`, no PVC copy step) is
> documented in `k8s/kubeopencode/dev-image/README.md`. That PR ships the
> Dockerfile + CI build validation only -- pushing it to a registry and
> setting `spec.executorImage` here is a manual follow-up, same as the rest
> of this section.

Check what was provisioned:

```bash
kubectl -n kubeopencode-system get pvc
```

### Resetting a corrupted or bloated workspace

Persistence means stale branches and build caches accumulate. To start clean,
delete the PVC and let the operator re-provision it (the init containers
re-clone):

```bash
kubectl -n kubeopencode-system delete pod <agent-pod>   # release the mount first
kubectl -n kubeopencode-system delete pvc <workspace-pvc>
```

> **Push before you reset.** Anything not pushed to a remote branch is gone.

## Files

- `agent.yaml` — the `Agent` CRD (`default-wf2`): `configRef` pointing at the
  `opencode-config` ConfigMap, credentials wiring (incl. the GitHub Copilot
  OAuth token), `spec.persistence` (workspace + sessions PVCs), and the pinned
  custom `agentImage` + `ghcr-pull` pull secret (BITB-172 — matches what the
  live object runs; see `k8s/kubeopencode/custom-opencode-image.md`)
- `agent-wf3.yaml` — the `Agent` CRD (`default-wf3`), same shape as
  `agent.yaml` (pinned `agentImage`, `ghcr-pull`, `configRef`, credentials,
  persistence); added in BITB-283 from the verified live spec
  (2026-11-09 export) so the second workflow agent is visible from the
  canonical deployment folder. Field-for-field identical to its
  `k8s/kubeopencode/agent-default-wf3.yaml` twin (both faithful to the same
  live object) — kept that way by `scripts/test_kubeopencode_manifests.py`
  (the BITB-171 anti-drift pattern). First apply is an owner-verified
  no-op diff.
- `agents.md` — documented 12-agent model table (mirrors the `agent` section of
  the generated `opencode.json`)

**Known gap (BITB-283):** the `desktop` Agent has no manifest here and its
only repo presence is an **unverified example sketch**
(`k8s/kubeopencode/agent-desktop.yaml` — no configRef, no credentials, no
`agentImage` pin; live runs the **unpinned**
`kubeopencode-agent-opencode:latest`, a binary-version contract risk).
Applying the sketch blindly would strip fields from the live object
(BITB-171 class). Export the live spec, diff it against the sketch, pin
`agentImage`, and promote a verified copy here — owner steps in the
[BITB-283 story](../../docs/BACKLOG_STORIES/BITB-283-agent-manifest-coverage-gap-wf3-desktop.md).

See also `k8s/kubeopencode/dev-image/` for the derivative agent image that
bakes in the in-pod dev toolchain (BITB-158).

## Notes

- `AgentSpec` has no top-level `model`/`provider` fields. All OpenCode settings
  (`model`, `small_model`, `provider`, `plugin`, per-agent models and
  `fallback_models`) live in the generated `opencode.json`, which reaches the
  pod via the `opencode-config` ConfigMap referenced by `spec.configRef`.
- `spec.config` (inline) and `configRef` are mutually exclusive
  (runtime-validated). `Agent` overrides template scalars and replaces lists.
  This deployment uses `configRef`, so there is no inline `spec.config` block.
- `.opencode/agents/*.md` is the single source of truth for per-agent `model`,
  `fallback_models`, `tools`, and `permission`. After editing an agent, run
  `make gen-opencode-config` and commit the regenerated `opencode.json`, then
  `make sync-opencode-configmap` to push it to the cluster.
- Fallback routing is executed by the `opencode-runtime-fallback@0.2.4` plugin
  configured in that generated file. Without the plugin, `fallback_models` is
  inert — `make verify-opencode-config` fails if either goes missing.
