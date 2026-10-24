# KubeOpenCode Agent Model Table (BITB-123)

Agent definitions live in `.opencode/agents/*.md` and are compiled into
`opencode.json` by `make gen-opencode-config`, which reaches KubeOpenCode
containers via the `opencode-config` ConfigMap (`spec.configRef`). This file
documents the model tiering held in that generated `agent` section (primary
`model` + `fallback_models`); the `.md` frontmatter is the source of truth.

| Agent | Primary model | Fallback 1 | Fallback 2 | Notes |
|---|---|---|---|---|
| orchestrator | `openrouter/z-ai/glm-5.3` | `opencode/nemotron-3-ultra-free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, cross‑provider free tier‑1, paid tier‑2 (retired gpt‑oss‑120b) |
| android-expert | `openrouter/z-ai/glm-5.3` | `opencode/nemotron-3-ultra-free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| fullstack-engineer | `openrouter/z-ai/glm-5.3` | `opencode/nemotron-3-ultra-free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| infra-engineer | `openrouter/z-ai/glm-5.3` | `opencode/nemotron-3-ultra-free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| android-gemini | `openrouter/z-ai/glm-5.3` | `opencode/nemotron-3-ultra-free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| data-engineer | `openrouter/z-ai/glm-5.3` | `opencode/nemotron-3-ultra-free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| verse-parity-keeper | `opencode/mimo-v2.6-flash-free` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/z-ai/glm-5.3` | Free primary, cross‑provider tier‑1, PAID tier‑2 |
| i18n-qa | `opencode/mimo-v2.6-flash-free` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/z-ai/glm-5.3` | Free primary, cross‑provider tier‑1, PAID tier‑2 |
| verifier | `openrouter/deepseek/deepseek-v3.2-exp` | `opencode/nemotron-3-ultra-free` | `openrouter/z-ai/glm-5.3` | PAID primary, free‑first‑paid‑last |
| risk-auditor | `openrouter/deepseek/deepseek-v3.2-exp` | `opencode/nemotron-3-ultra-free` | `openrouter/z-ai/glm-5.3` | PAID primary, free‑first‑paid‑last |
| failure-forecaster | `openrouter/deepseek/deepseek-v3.2-exp` | `opencode/nemotron-3-ultra-free` | `openrouter/z-ai/glm-5.3` | PAID primary, free‑first‑paid‑last |
| seo-auditor | `openrouter/deepseek/deepseek-v3.2-exp` | `opencode/nemotron-3-ultra-free` | `openrouter/z-ai/glm-5.3` | PAID primary, free‑first‑paid‑last |

Fallbacks are served by the `opencode-runtime-fallback@0.2.4` plugin, configured
in the generated `opencode.json` (retry on
`[400, 401, 402, 403, 429, 500, 502, 503, 504]` — auth/quota 4xx included so an
exhausted-subscription provider still fails over, **2 attempts**, 120 s cooldown,
45 s timeout, notify on fallback).

## Cross-provider resilience (2-hop fallback)

Every agent has a **2-hop fallback chain — free first, paid last** (BITB-173)
so routine failovers cost nothing and a provider outage degrades instead of
killing the agent graph:

1. **Primary**: the strongest **paid** model on the graph —
   `openrouter/z-ai/glm-5.3` (high‑performance paid tier) —
   powers the global model (builtins: build/plan/general/explore/compaction/
   title/summary) and the orchestrator. Cheap ops (`small_model`: titles,
   compaction) stay on Zen free, off the OpenRouter free‑tier rate limits.
2. **Tier 1 (free, cross‑provider)**: the hop is always on the OTHER provider
   than the primary — OpenRouter primaries (global builtins, orchestrator,
   android‑gemini) fail over to `opencode/nemotron-3-ultra-free` (Zen); Zen
   primaries (the specialist subagents) fail over to
   `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (OpenRouter). A full
   outage of either provider never kills the chain.
3. **Tier 2 (paid)**: the alternative paid OpenRouter model for the lane —
   `openrouter/deepseek/deepseek-v3.2-exp` (paid, other OpenRouter model) —
   engages only when both free hops fail, so cost is bounded to double‑failure events.

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
