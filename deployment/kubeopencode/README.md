# KubeOpenCode Deployment Config

Adhoc folder for the KubeOpenCode `Agent` manifest. Agent behaviour lives in
`.opencode/agents/*.md`; this folder holds only the cluster-side wiring
(models, fallbacks, plugin, provider timeouts, credentials).

## Prerequisites

- KubeOpenCode v0.1.8+ installed (supports `configRef` / inline `config`)
- Namespace `kubeopencode-system` exists
- Secret `ai-credentials` with key `api-key` in `kubeopencode-system`
  → injected as `OPENCODE_API_KEY`
- Secret `openrouter-api-key` with key `openrouter-api-key` in
  `kubeopencode-system` → injected as `OPENROUTER_API_KEY` (required:
  `android-gemini` uses paid-tier primary `openrouter/qwen/qwen3-coder`;
  without it the agent falls back to `opencode/muse-spark-1.3-contributor-free`)
- Secret `github-copilot-auth` with key `token` in `kubeopencode-system`
  → injected as `GITHUB_TOKEN` (see [Persist GitHub Copilot access](#persist-github-copilot-access))

### Create the secret

```bash
# Ensure namespace exists
kubectl create namespace kubeopencode-system --dry-run=client -o yaml | kubectl apply -f -

# OpenCode API key (replace with a real key)
kubectl -n kubeopencode-system create secret generic ai-credentials \
  --from-literal=api-key="YOUR_OPENCODE_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# OpenRouter key lives in its own secret (see agent.yaml credentials)
kubectl -n kubeopencode-system create secret generic openrouter-api-key \
  --from-literal=openrouter-api-key="YOUR_OPENROUTER_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Apply

```bash
kubectl apply -f deployment/kubeopencode/agent.yaml
kubectl -n kubeopencode-system get agent default-wf2
```

## Persist GitHub Copilot access

`/connect` stores OAuth in `~/.local/share/opencode/auth.json` (ephemeral,
lost on pod restart). `persistence.sessions/workspace` preserves DB/files,
not auth. Inject `GITHUB_TOKEN` declaratively so it survives restarts:

```bash
kubectl create secret generic github-copilot-auth -n kubeopencode-system \
  --from-literal=token=ghp_... # pragma: allowlist secret
```

`agent.yaml` already wires it:

```yaml
credentials:
  - name: github-copilot
    secretRef:
      name: github-copilot-auth
      key: token
    env: GITHUB_TOKEN
```

Requires a Copilot subscription with chat enabled; OpenCode exchanges and
refreshes the bearer token automatically.

## Files

- `agent.yaml` — the `Agent` CRD (`default-wf2`): primary + small models,
  `opencode-runtime-fallback@0.2.4` plugin, provider timeout options,
  credentials wiring, per-agent `fallbackModels` including the orchestrator
- `agents.md` — documented 12-agent model table (mirrors `spec.config.agent`)

## Notes

- `AgentSpec` has no top-level `model`/`provider` fields — all OpenCode
  settings (`model`, `small_model`, `provider`, per-agent models/fallbacks)
  live under `spec.config`, which is serialized to `opencode.json` in the pod.
- `spec.config` (inline) and `configRef` are mutually exclusive
  (runtime-validated). `Agent` overrides template scalars and replaces lists.
- Keep `spec.config.agent` in sync with `.opencode/agents/*.md` when adding or
  renaming agents: the `.md` files hold definitions, the YAML holds models and
  fallbacks.
