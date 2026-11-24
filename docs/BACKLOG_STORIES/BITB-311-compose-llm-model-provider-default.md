---
id: BITB-311
status: in-review
priority: P2
size: XS
rank: 10
created: 2026-11-13
---

# BITB-311: Docker Compose Always Sets LLM_MODEL, So `LLM_PROVIDER=claude` Gets an Ollama Model Name

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

- [x] `LLM_PROVIDER=claude` under `make docker-up` uses the Claude default model
- [x] The local Ollama stack still starts with its existing default model

## Implementation

- `Settings` drops a blank/whitespace `LLM_MODEL` / `OLLAMA_LLM_MODEL` (before-validator), so it is
  not in `model_fields_set`. New optional `ollama_llm_model` (`OLLAMA_LLM_MODEL`).
- `providers/factory.py::_ollama_model` (shared by `create_llm_provider` and `effective_llm_model`):
  explicit `LLM_MODEL`, else `OLLAMA_LLM_MODEL`, else `llama3:8b`. Claude unchanged.
- Compose `api` services: `LLM_MODEL=${LLM_MODEL:-}`; `docker-compose.yml` / `.dev.yml` add
  `OLLAMA_LLM_MODEL` defaulting to `mistral:7b`. local-prod files just drop the OpenRouter slug default.
- Tests: `tests/test_runtime_alignment.py` (blank/Claude/Ollama resolution),
  `tests/test_compose_llm_model_default.py` (compose files).
- Checked, no follow-up needed: `docker-compose.yml`'s Ollama container still reads
  `${LLM_MODEL:-mistral:7b}`, but `scripts/init-ollama.sh` only pulls it when `LLM_PROVIDER=ollama`,
  so a Claude model ID is never pulled.
