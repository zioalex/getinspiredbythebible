# KubeOpenCode Agent Model Table (BITB-123)

Agent definitions live in `.opencode/agents/*.md` and are compiled into
`opencode.json` by `make gen-opencode-config`, which reaches KubeOpenCode
containers via the `opencode-config` ConfigMap (`spec.configRef`). This file
documents the model tiering held in that generated `agent` section (primary
`model` + `fallback_models`); the `.md` frontmatter is the source of truth.

| Agent | Primary model | Fallback 1 | Fallback 2 (cross-provider) | Notes |
|---|---|---|---|---|---|
| orchestrator | `github-copilot/claude-opus-5` (paid) | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Primary planner; 2-hop fallback |
| android-expert | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Kotlin/Compose builder; cross-provider resilient |
| fullstack-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | FastAPI/Next.js/PG builder; cross-provider resilient |
| infra-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Azure/Terraform/CI builder; cross-provider resilient |
| android-gemini | `openrouter/qwen/qwen3-coder` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Paid-tier coder (BITB-023); needs `OPENROUTER_API_KEY` |
| data-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | pgvector/Alembic/embeddings; cross-provider resilient |
| verse-parity-keeper | `opencode/mimo-v2.5-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | 3 parsers in sync, 11 languages; cross-provider resilient |
| i18n-qa | `opencode/mimo-v2.5-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Locales/translations QA; cross-provider resilient |
| verifier | `github-copilot/claude-opus-5` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Read-only test runner; 2-hop fallback |
| risk-auditor | `github-copilot/claude-opus-5` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Read-only audit; 2-hop fallback |
| failure-forecaster | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Read-only 12-month forecast; cross-provider resilient |
| seo-auditor | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Read-only SEO audit; cross-provider resilient |

Fallbacks are served by the `opencode-runtime-fallback@0.2.4` plugin, configured
in the generated `opencode.json` (retry on
`[429, 500, 502, 503, 504]`, **2 attempts**, 120 s cooldown, 45 s timeout, notify on
fallback).

## Cross-provider resilience (2-hop fallback)

Every agent now has a **2-hop fallback chain spanning two providers** so a
single provider outage cannot take down the entire agent graph:

1. **Tier 1**: `opencode/muse-spark-1.3-contributor-free` (OpenCode Zen) —
   fastest recovery within the same provider family.
2. **Tier 2**: `openrouter/google/gemma-3-27b-it:free` (OpenRouter) —
   cross-provider free model that activates only if Tier 1 also fails (e.g.
   OpenCode Zen is entirely down).

The 3-tier coverage matrix:

| Failure scenario | Orchestrator/risk/verifier (GitHub prim) | Builders (OpenCode prim) | android-gemini (OpenRouter prim) |
|---|---|---|---|
| GitHub Copilot down | Falls back to OpenCode Zen → OpenRouter | Unaffected | Unaffected |
| OpenCode Zen down | Falls back to OpenRouter | Falls back to OpenRouter | Unaffected |
| OpenRouter down | Unaffected | Unaffected | Falls back to OpenCode Zen → OpenRouter |
| 2 of 3 providers down | Survives if 1 provider remains | Survives if 1 provider remains | Survives if 1 provider remains |

`max_fallback_attempts` is set to `2` (up from `1`) to allow the
full 2-hop chain. Project is open source, so NVIDIA trial-model data logging
on the `nemotron` models and OpenRouter free-tier data collection are
acceptable.

## Approved exception to the Plan → Build → Verify relay

`AGENTS.md` assigns the Build stage to Sonnet and final verification to Opus.
This graph intentionally uses free-tier builders (`nemotron-3-ultra-free`,
`mimo-v2.5-free`, `qwen3-coder`) for routine implementation, reserving paid
Opus 5 for the stages where reasoning quality is load-bearing: orchestration,
risk audit, and independent verification. This exception was approved in
BITB-123 review.
