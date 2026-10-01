# KubeOpenCode Agent Model Table (BITB-123)

Agent definitions live in `.opencode/agents/*.md` and are compiled into
`opencode.json` by `make gen-opencode-config`, which reaches KubeOpenCode
containers via the `opencode-config` ConfigMap (`spec.configRef`). This file
documents the model tiering held in that generated `agent` section (primary
`model` + `fallback_models`); the `.md` frontmatter is the source of truth.

| Agent | Primary model | Fallback 1 | Fallback 2 (cross-provider) | Notes |
|---|---|---|---|---|---|
| orchestrator | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Primary planner; 2-hop fallback |
| android-expert | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Kotlin/Compose builder; cross-provider resilient |
| fullstack-engineer | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | FastAPI/Next.js/PG builder; cross-provider resilient |
| infra-engineer | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Azure/Terraform/CI builder; cross-provider resilient |
| android-gemini | `openrouter/qwen/qwen3-coder` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Paid-tier coder (BITB-023); needs `OPENROUTER_API_KEY` |
| data-engineer | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | pgvector/Alembic/embeddings; cross-provider resilient |
| verse-parity-keeper | `opencode/mimo-v2.6-flash-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | 3 parsers in sync, 11 languages; cross-provider resilient |
| i18n-qa | `opencode/mimo-v2.6-flash-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Locales/translations QA; cross-provider resilient |
| verifier | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Read-only test runner; 2-hop fallback |
| risk-auditor | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Read-only audit; 2-hop fallback |
| failure-forecaster | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Read-only 12-month forecast; cross-provider resilient |
| seo-auditor | `opencode/nemotron-3-ultra-free` | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | `openrouter/openai/gpt-oss-120b` | Read-only SEO audit; cross-provider resilient |

Fallbacks are served by the `opencode-runtime-fallback@0.2.4` plugin, configured
in the generated `opencode.json` (retry on
`[400, 401, 402, 403, 429, 500, 502, 503, 504]` — auth/quota 4xx included so an
exhausted-subscription provider still fails over, **2 attempts**, 120 s cooldown,
45 s timeout, notify on fallback).

## Cross-provider resilience (2-hop fallback)

Every agent has a **2-hop fallback chain — free first, paid last** (BITB-173)
so routine failovers cost nothing and a provider outage degrades instead of
killing the agent graph:

1. **Tier 1 (free)**: `openrouter/nvidia/nemotron-3-super-120b-a12b:free`
   (OpenRouter) — the free Nemotron-3-Super 120B-A12B variant. OpenCode Zen
   serves no Super variant (its Nemotron lineup is ultra + 3.5-lightning), so
   the free hop lives on the provider that actually serves it. Being a
   different provider from the Zen primary, it survives a full Zen outage.
2. **Tier 2 (paid)**: `openrouter/openai/gpt-oss-120b` (OpenRouter,
   ~$0.10/$0.40 per 1M tokens) — the paid safety net that engages only when
   both free hops fail, so cost is bounded to double-failure events.

The 3-tier coverage matrix:

| Failure scenario | Zen-primary agents (11) | android-gemini (OpenRouter prim) |
|---|---|---|
| OpenCode Zen down (e.g. NVIDIA upstream 503) | Falls back to OpenRouter (tier 1 → 2) | Unaffected |
| OpenRouter down | Unaffected | Whole chain down — accepted trade-off, see note below |
| Both down | Agent down (no third provider in the graph) | Agent down |

> **Note (BITB-173):** android-gemini's entire chain (primary + both
> fallbacks) now lives on OpenRouter. The pre-BITB-173 chain *intended* its
> tier-1 to be a Zen model, but that ID never existed (`opencode/nemotron-3-super-free`)
> and the free Super variant is only served by OpenRouter, so there is no
> valid free Zen hop to restore. OpenRouter gateway outages take this one
> agent down while the 11 Zen-primary agents keep working. Revisit if Zen
> ever adds a mid-tier free Nemotron.

`max_fallback_attempts` is set to `2` to allow the full 2-hop chain. Project
is open source, so NVIDIA trial-model data logging on the `nemotron` models
and OpenRouter free-tier data collection are acceptable.

> **Note (2026-09-14):** `github-copilot/claude-opus-5` was previously the
> primary for orchestrator, verifier, and risk-auditor. It was moved to
> `opencode/nemotron-3-ultra-free` after the Copilot subscription credits were
> exhausted — the Copilot provider stopped serving requests and those three
> agents returned empty responses. Restore the paid model (and this matrix) if
> Copilot access returns.

## Approved exception to the Plan → Build → Verify relay

`AGENTS.md` assigns the Build stage to Sonnet and final verification to Opus.
This graph uses free-tier models throughout (`nemotron-3-ultra-free`,
`mimo-v2.6-flash-free`) and the free `nemotron-3-super` OpenRouter fallback
(BITB-173) for every stage, with the paid `qwen3-coder` (OpenRouter) as the sole
paid primary for the Google/Jetpack-heavy Android agent. No paid Opus is
currently reserved for orchestration/verification because Copilot access is
unavailable; `nemotron-3-ultra-free` is the strongest free model and covers
those reasoning-heavy roles. This exception was approved in BITB-123 review and
adjusted on 2026-09-14 and 2026-10-01.

## Paid-model provider convention

Paid (non-`:free`/`-free`) models are always served via **OpenRouter** — the
only provider in this graph backed by our own key/credits (`OPENROUTER_API_KEY`).
`scripts/generate-opencode-config.py::enforce_openrouter_for_paid` fails
generation loudly if a billable model is ever attached to another provider, so
a repeat of the `github-copilot/claude-opus-5` outage (paid primary on a
subscription-credit provider, empty responses when credits ran out) cannot land
silently. Free-tier models may live on any provider.
