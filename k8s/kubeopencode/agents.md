# KubeOpenCode Agent Model Table (BITB-123)

Agent definitions live in `.opencode/agents/*.md` and are compiled into
`opencode.json` by `make gen-opencode-config`, which reaches KubeOpenCode
containers via the `opencode-config` ConfigMap (`spec.configRef`). This file
documents the model tiering held in that generated `agent` section (primary
`model` + `fallback_models`); the `.md` frontmatter is the source of truth.

| Agent | Primary model | Fallback 1 | Fallback 2 | Notes |
|---|---|---|---|---|
| orchestrator | `openrouter/z-ai/glm-5.3` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free tier‑1 (survives key exhaustion), paid tier‑2 (retired gpt‑oss‑120b) |
| android-expert | `openrouter/z-ai/glm-5.3` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| fullstack-engineer | `openrouter/z-ai/glm-5.3` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| infra-engineer | `openrouter/z-ai/glm-5.3` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| android-gemini | `openrouter/z-ai/glm-5.3` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| data-engineer | `openrouter/z-ai/glm-5.3` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/deepseek/deepseek-v3.2-exp` | PAID primary, free‑first‑paid‑last |
| verse-parity-keeper | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/nvidia/nemotron-3.5-lightning:free` | `openrouter/z-ai/glm-5.3` | Free primary + de‑duplicated free tier‑1, PAID tier‑2 |
| i18n-qa | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/nvidia/nemotron-3.5-lightning:free` | `openrouter/z-ai/glm-5.3` | Free primary + de‑duplicated free tier‑1, PAID tier‑2 |
| verifier | `openrouter/deepseek/deepseek-v3.2-exp` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/z-ai/glm-5.3` | PAID primary, free‑first‑paid‑last |
| risk-auditor | `openrouter/deepseek/deepseek-v3.2-exp` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/z-ai/glm-5.3` | PAID primary, free‑first‑paid‑last |
| failure-forecaster | `openrouter/deepseek/deepseek-v3.2-exp` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/z-ai/glm-5.3` | PAID primary, free‑first‑paid‑last |
| seo-auditor | `openrouter/deepseek/deepseek-v3.2-exp` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | `openrouter/z-ai/glm-5.3` | PAID primary, free‑first‑paid‑last |

Fallbacks are served by the `opencode-runtime-fallback@0.2.4` plugin, configured
in the generated `opencode.json` (retry on
`[400, 401, 402, 403, 429, 500, 502, 503, 504]` — auth/quota 4xx included so an
exhausted-subscription provider still fails over, **2 attempts**, 120 s cooldown,
45 s timeout, notify on fallback).

## Fallback resilience (2-hop chain)

Every agent has a **2-hop fallback chain — free first, paid last** (BITB-173)
so routine failovers cost nothing and a failure degrades instead of killing
the agent graph:

1. **Primary**: the lane's strongest **paid** model —
   `openrouter/z-ai/glm-5.3` (workhorse/builders, the orchestrator, and the
   global model that powers the builtins: build/plan/general/explore/
   compaction/title/summary) or `openrouter/deepseek/deepseek-v3.2-exp`
   (skeptics). Cheap ops (`small_model`: titles, compaction) run on the
   light free `openrouter/nvidia/nemotron-3.5-lightning:free`, off the
   paid key.
2. **Tier 1 (free)**: always a free `openrouter/:free` nemotron — the
   strong `nemotron-3-ultra-550b-a55b:free` for the paid lanes, and
   `nemotron-3.5-lightning:free` for the mechanical lanes (where the ultra
   model is itself the primary, so the hop de-duplicates). BITB-279
   (2026-11-08 key-exhaustion incident): free models draw no credit, so
   this hop keeps serving while the paid key is exhausted. Cross-provider
   hops are impossible — OpenRouter is the only provider with credentials
   here and the only free slate (12 `nvidia/nemotron-*:free` variants).
3. **Tier 2 (paid)**: the lane's other paid OpenRouter model —
   `openrouter/deepseek/deepseek-v3.2-exp` for GLM lanes,
   `openrouter/z-ai/glm-5.3` for the rest — engages only after the primary
   and the free tier-1 both fail (free-tier rate caps, upstream 5xx/429),
   so cost is bounded to double-failure events.

The failure-coverage matrix (single provider — OpenRouter is the only
credentialed provider in this graph):

| Failure scenario | Effect on the chain |
|---|---|
| Paid key exhausted (e.g. weekly OpenRouter limit — the 2026-11-08 21:30 incident) | Free tier-1 absorbs traffic; agents keep serving at zero credit |
| Free-model rate caps / upstream 5xx/429 | Paid tier-2 rescues |
| OpenRouter gateway fully down | Whole graph down — accepted single-provider trade-off; revisit if a second credentialed provider is ever added |

> **Note (BITB-173, historical):** the pre-BITB-173 chain *intended* its
> tier-1 to be a free Zen model, but that ID (`opencode/nemotron-3-super-free`)
> never existed on the Zen gateway — the free Super variant was only served
> by OpenRouter. The BITB-279 incident later proved the whole Zen gateway
> unservable in this pod (no credentials), retiring the last `opencode/*`
> references. Kept as the worked example of why model IDs must be verified
> against the live catalog (`opencode models`), never the docs.

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
No Claude-Opus lane exists in this graph: since the Copilot subscription
credits ran out (2026-09-14), the paid lanes run on `openrouter/z-ai/glm-5.3`
(planning/build, BITB-236) and `openrouter/deepseek/deepseek-v3.2-exp`
(verification/audit), with free `openrouter/nvidia/nemotron-*:free` tier-1
hops (BITB-279). This exception was approved in BITB-123 review and adjusted
on 2026-09-14, 2026-10-01 (BITB-236), and 2026-11-08 (BITB-279).

## Paid-model provider convention

Paid (non-`:free`/`-free`) models are always served via **OpenRouter** — the
only provider in this graph backed by our own key/credits (`OPENROUTER_API_KEY`).
`scripts/generate-opencode-config.py::enforce_openrouter_for_paid` fails
generation loudly if a billable model is ever attached to another provider, so
a repeat of the `github-copilot/claude-opus-5` outage (paid primary on a
subscription-credit provider, empty responses when credits ran out) cannot land
silently. Free-tier models may live on any provider.
