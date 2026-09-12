# KubeOpenCode Deployment Config

Adhoc folder for the KubeOpenCode `Agent` manifest. Agent behaviour, models,
and fallbacks live in `.opencode/agents/*.md` and are compiled into
`opencode.json` by `make gen-opencode-config`; this folder holds only the
cluster-side wiring (the `configRef` pointer and credentials).

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

- `agent.yaml` — the `Agent` CRD (`default-wf`): `configRef` pointing at the
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
