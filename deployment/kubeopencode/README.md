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

## Persistence (BITB-128)

`spec.persistence` in `agent.yaml` backs the agent with operator-managed PVCs.
Without it the workspace is an `EmptyDir`, so the `kubectl delete pod` step above
— which this runbook *requires* after every config sync — destroys the clone, any
uncommitted work, and the conversation history.

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
  `opencode-config` ConfigMap, plus credentials wiring
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
