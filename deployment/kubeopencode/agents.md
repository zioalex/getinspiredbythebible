# KubeOpenCode Agent Model Table (BITB-123)

Agent definitions live in `.opencode/agents/*.md` and are compiled into
`opencode.json` by `make gen-opencode-config`, which reaches KubeOpenCode
containers via the `opencode-config` ConfigMap (`spec.configRef`). This file
documents the model tiering held in that generated `agent` section (primary
`model` + `fallback_models`); the `.md` frontmatter is the source of truth.

| Agent | Primary model | Fallback 1 | Fallback 2 (cross-provider) | Notes |
|---|---|---|---|---|---|
| orchestrator | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Primary planner; 2-hop fallback |
| android-expert | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Kotlin/Compose builder; cross-provider resilient |
| fullstack-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | FastAPI/Next.js/PG builder; cross-provider resilient |
| infra-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Azure/Terraform/CI builder; cross-provider resilient |
| android-gemini | `openrouter/qwen/qwen3-coder` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Paid-tier coder (BITB-023); needs `OPENROUTER_API_KEY` |
| data-engineer | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | pgvector/Alembic/embeddings; cross-provider resilient |
| verse-parity-keeper | `opencode/mimo-v2.5-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | 3 parsers in sync, 11 languages; cross-provider resilient |
| i18n-qa | `opencode/mimo-v2.5-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Locales/translations QA; cross-provider resilient |
| verifier | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Read-only test runner; 2-hop fallback |
| risk-auditor | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Read-only audit; 2-hop fallback |
| failure-forecaster | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Read-only 12-month forecast; cross-provider resilient |
| seo-auditor | `opencode/nemotron-3-ultra-free` | `opencode/muse-spark-1.3-contributor-free` | `openrouter/google/gemma-3-27b-it:free` | Read-only SEO audit; cross-provider resilient |

Fallbacks are served by the `opencode-runtime-fallback@0.2.4` plugin, configured
in the generated `opencode.json` (retry on
`[400, 401, 402, 403, 429, 500, 502, 503, 504]` — auth/quota 4xx included so an
exhausted-subscription provider still fails over, **2 attempts**, 120 s cooldown,
45 s timeout, notify on fallback).

## Cross-provider resilience (2-hop fallback)

Every agent now has a **2-hop fallback chain spanning two providers** so a
single provider outage cannot take down the entire agent graph:

1. **Tier 1**: `opencode/muse-spark-1.3-contributor-free` (OpenCode Zen) —
   fastest recovery within the same provider family.
2. **Tier 2**: `openrouter/google/gemma-3-27b-it:free` (OpenRouter) —
   cross-provider free model that activates only if Tier 1 also fails (e.g.
   OpenCode Zen is entirely down).

The 3-tier coverage matrix:

| Failure scenario | All agents (OpenCode prim) | android-gemini (OpenRouter prim) |
|---|---|---|
| OpenCode Zen down | Falls back to OpenRouter (gemma) | Unaffected |
| OpenRouter down | Unaffected | Falls back to OpenCode → OpenRouter |
| Both down | Survives on last remaining provider | Survives on last remaining provider |

`max_fallback_attempts` is set to `2` (up from `1`) to allow the
full 2-hop chain. Project is open source, so NVIDIA trial-model data logging
on the `nemotron` models and OpenRouter free-tier data collection are
acceptable.

> **Note (2026-09-14):** `github-copilot/claude-opus-5` was previously the
> primary for orchestrator, verifier, and risk-auditor. It was moved to
> `opencode/nemotron-3-ultra-free` after the Copilot subscription credits were
> exhausted — the Copilot provider stopped serving requests and those three
> agents returned empty responses. Restore the paid model (and this matrix) if
> Copilot access returns.

## Approved exception to the Plan → Build → Verify relay

`AGENTS.md` assigns the Build stage to Sonnet and final verification to Opus.
This graph uses free-tier models throughout (`nemotron-3-ultra-free`,
`mimo-v2.5-free`) for every stage, with `qwen3-coder` (OpenRouter) as the sole
paid primary for the Google/Jetpack-heavy Android agent. No paid Opus is
currently reserved for orchestration/verification because Copilot access is
unavailable; `nemotron-3-ultra-free` is the strongest free model and covers
those reasoning-heavy roles. This exception was approved in BITB-123 review and
adjusted on 2026-09-14.

## Paid-model provider convention

Paid (non-`:free`/`-free`) models are always served via **OpenRouter** — the
only provider in this graph backed by our own key/credits (`OPENROUTER_API_KEY`).
`scripts/generate-opencode-config.py::enforce_openrouter_for_paid` fails
generation loudly if a billable model is ever attached to another provider, so
a repeat of the `github-copilot/claude-opus-5` outage (paid primary on a
subscription-credit provider, empty responses when credits ran out) cannot land
silently. Free-tier models may live on any provider.
