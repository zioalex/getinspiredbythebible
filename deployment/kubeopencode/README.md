# KubeOpenCode Deployment Config

Adhoc folder for the KubeOpenCode `Agent` manifest. Agent behaviour lives in
`.opencode/agents/*.md`; this folder holds only the cluster-side wiring
(models, fallbacks, plugin, provider timeouts, credentials).

## Prerequisites

- KubeOpenCode v0.1.8+ installed (supports `configRef` / inline `config`)
- Secret `ai-credentials` with key `api-key` in namespace `kubeopencode-system`
- `OPENROUTER_API_KEY` available if `android-gemini` should use its paid-tier
  primary (`openrouter/qwen/qwen3-coder`); otherwise it falls back to
  `opencode/muse-spark-1.3-contributor-free`

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

- `spec.config` (inline) and `configRef` are mutually exclusive
  (runtime-validated). `Agent` overrides template scalars and replaces lists.
- Keep `spec.config.agent` in sync with `.opencode/agents/*.md` when adding or
  renaming agents: the `.md` files hold definitions, the YAML holds models and
  fallbacks.
