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
  `kubeopencode-system` → injected as `OPENROUTER_API_KEY` (required:
  `android-gemini` uses paid-tier primary `openrouter/qwen/qwen3-coder`;
  without it the agent falls back to `opencode/muse-spark-1.3-contributor-free`)
- Secret `github-copilot-auth` in `kubeopencode-system` → Copilot credential
  for the `github-copilot/*` models (orchestrator, verifier, risk-auditor).
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
# Regenerate opencode.json from .opencode/agents/*.md, verify it, and
# create/update the ConfigMap in one step.
make sync-opencode-configmap
```

That target runs `verify-opencode-config` first, so a config missing agents,
`fallback_models`, or the fallback plugin fails before it can reach the
cluster. The equivalent raw command, if you are not using the Makefile:

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

## Apply

Apply the Agent **after** the namespace, secrets, and ConfigMap above exist:

```bash
kubectl apply -f deployment/kubeopencode/agent.yaml
kubectl -n kubeopencode-system get agent default-wf2
```

If the Agent stays unready, check that the ConfigMap it references is present:

```bash
kubectl -n kubeopencode-system get configmap opencode-config
kubectl -n kubeopencode-system describe agent default-wf2
```

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
  OAuth token), and `spec.persistence` (workspace + sessions PVCs)
- `agents.md` — documented 12-agent model table (mirrors the `agent` section of
  the generated `opencode.json`)

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
