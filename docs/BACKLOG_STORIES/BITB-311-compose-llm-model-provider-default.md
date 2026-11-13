# BITB-311: Docker Compose Always Sets LLM_MODEL, So `LLM_PROVIDER=claude` Gets an Ollama Model Name

**Status:** 🎯 Todo
**Priority:** P2
**Size:** XS
**Created:** 2026-11-13
**Prompted by:** BITB-304 build (follow-up).

## Problem

BITB-304 made `LLM_PROVIDER=claude` use the Claude provider's own default model unless the
operator explicitly sets `LLM_MODEL` (`api/providers/factory.py`, `model_fields_set`). The
Compose files bypass that: they always inject a value, so in Compose the model counts as
"explicitly set" even when the operator set nothing.

- `docker-compose.yml:13,56` and `docker-compose.dev.yml:27`: `LLM_MODEL=${LLM_MODEL:-mistral:7b}`
- `docker-compose.local-prod.yml:21` and `docker-compose.local-prod-acr-be.yml:25`:
  `LLM_MODEL=${LLM_MODEL:-meta-llama/llama-3.1-8b-instruct:free}`

Result: `LLM_PROVIDER=claude make docker-up` sends `mistral:7b` to Anthropic and every chat fails.
Env, `.env` and Azure/k8s deployments are not affected.

## Requirements

1. In the backend service, pass `LLM_MODEL` through only when the operator set it. Use
   `${LLM_MODEL:-}` and treat an empty string as unset in `Settings`, or drop the default
   and let each provider default apply. Keep the Ollama defaults the local stack relies on.
2. Leave the Ollama container's own `LLM_MODEL=${OLLAMA_LLM_MODEL:-...}` unchanged.
3. Update `docs/LOCAL_DEVELOPMENT.md` if it documents the Compose default.

## Tests

- `Settings` with `LLM_MODEL=""` and `LLM_PROVIDER=claude` builds a `ClaudeProvider`
  that uses `DEFAULT_CLAUDE_MODEL`.
- A Compose-file test asserting that no backend service hard-defaults `LLM_MODEL` to a
  provider-specific value.

## Acceptance criteria

- [ ] `LLM_PROVIDER=claude` under `make docker-up` uses the Claude default model
- [ ] The local Ollama stack still starts with its existing default model
