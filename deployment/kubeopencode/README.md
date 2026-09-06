# KubeOpenCode Deployment Config

Adhoc folder for the KubeOpenCode `Agent` manifest. Agent behaviour lives in
`.opencode/agents/*.md`; this folder holds only the cluster-side wiring
(models, fallbacks, plugin, provider timeouts, credentials).

## Prerequisites

- KubeOpenCode v0.1.8+ installed (supports `configRef` / inline `config`)
- Namespace `kubeopencode-system` exists
- Secret `ai-credentials` in `kubeopencode-system` with keys:
  - `api-key` → injected as `OPENCODE_API_KEY`
  - `openrouter-api-key` → injected as `OPENROUTER_API_KEY` (required:
    `android-gemini` uses paid-tier primary `openrouter/qwen/qwen3-coder`;
    without it the agent falls back to `opencode/muse-spark-1.3-contributor-free`)

### Create the secret

```bash
# Ensure namespace exists
kubectl create namespace kubeopencode-system --dry-run=client -o yaml | kubectl apply -f -

# Create secret from literal values (replace with real keys)
kubectl -n kubeopencode-system create secret generic ai-credentials \
  --from-literal=api-key="YOUR_OPENCODE_API_KEY" \
  --from-literal=openrouter-api-key="YOUR_OPENROUTER_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Or from files
# kubectl -n kubeopencode-system create secret generic ai-credentials \
#   --from-file=api-key=/path/to/opencode-key \
#   --from-file=openrouter-api-key=/path/to/openrouter-key \
#   --dry-run=client -o yaml | kubectl apply -f -
```

## Apply

```bash
kubectl apply -f deployment/kubeopencode/agent.yaml
kubectl -n kubeopencode-system get agent default-wf
```

## Files

- `agent.yaml` — the `Agent` CRD (`default-wf`): primary + small models,
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
