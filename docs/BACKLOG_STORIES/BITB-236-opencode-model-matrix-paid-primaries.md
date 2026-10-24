# BITB-236: Agent Model Matrix 2.0 — Paid Primaries (GLM-5.3 Workhorse + DeepSeek-V3.2-Exp Skeptic)

**Priority:** P2 (Medium)
**Status:** 🚧 In Progress
**Size:** M
**Created:** 2026-10-24

---

## Background

The agent graph has run entirely on free-tier primaries since BITB-123/173: every
implementation lane was `opencode/nemotron-3-ultra-free` with
`openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` as first fallback — the same
congested free pool for primary AND tier-1, which is the root cause of the
dispatch-time 503 storms the BITB-169 task-reliability protocol was built to
survive (detached subagent sessions, cancelled task calls, duplicate work).

The owner decided to introduce **two paying models** on OpenRouter and asked for
a role-mapped placement:

- **GLM-5.3** (`openrouter/z-ai/glm-5.3` — $0.89/$2.80 per 1M, 1.31M context,
  reasoning always on) as the **workhorse**: orchestrator + all builders.
- A **DeepSeek reasoning model** as the **skeptic**: verifier + read-only auditors.
  Live-catalog check (`opencode models`, 2026-10-24) found
  `deepseek/deepseek-reasoner` **no longer exists** — the docs' mapping is stale
  (the exact BITB-173 trap). The live reasoning-class successor is
  `openrouter/deepseek/deepseek-v3.2-exp`, which dominates R1-0528 on our own
  benchmark sheet on both axes (74.2% vs 71.4% Aider Pass@2; $1.30 vs $4.80 per
  run), so it takes the skeptic seat. `deepseek-r1-0528` remains a valid swap.

Additionally:

- **gpt-oss-120b is retired everywhere** (owner decision): 41.8% Aider — the
  weakest coder on the ranking sheet, yet the tier-2 paid hop on every chain.
  It goes into the BITB-173 stale-ID tripwire.
- **Nemotron free keeps real seats** (owner requirement): it stays the
  tier-1 cross-provider rescue hop for the entire paid fleet, the `small_model`
  for cheap ops, and (OpenRouter variant) tier-1 on the mechanical lanes.
  What goes away is only its role as *primary on high-stakes lanes* — the seat
  that caused the 503 storms.

All model IDs in this story were verified against the live catalog
(`opencode models`) on 2026-10-24, per the BITB-173 rule that the gateway, not
the docs, is the source of truth.

---

## User Story

**As a** developer running the Plan → Build → Verify relay,
**I want** high-stakes lanes on paid, SLA-backed primaries with the free tier
demoted to mechanical lanes and rescue hops,
**so that** dispatch-time 503s stop detaching subagent sessions while routine
failovers stay free and the strongest reasoning sits in the verification seat
where false-greens are the most expensive failure.

---

## The Matrix

| Lane | Agents | Primary (paid) | Tier-1 (free, cross-provider) | Tier-2 (paid) |
|---|---|---|---|---|
| Workhorse | orchestrator | `openrouter/z-ai/glm-5.3` | `opencode/nemotron-3-ultra-free` | `openrouter/deepseek/deepseek-v3.2-exp` |
| Builders | fullstack-engineer, android-expert, android-gemini, infra-engineer, data-engineer | `openrouter/z-ai/glm-5.3` | `opencode/nemotron-3-ultra-free` | `openrouter/deepseek/deepseek-v3.2-exp` |
| Skeptics | verifier, risk-auditor, failure-forecaster, seo-auditor | `openrouter/deepseek/deepseek-v3.2-exp` | `opencode/nemotron-3-ultra-free` | `openrouter/z-ai/glm-5.3` |
| Mechanical (free) | i18n-qa, verse-parity-keeper | `opencode/mimo-v2.6-flash-free` (unchanged) | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (unchanged) | `openrouter/z-ai/glm-5.3` |

Global generator constants: `DEFAULT_MODEL` (builtins: build/plan/general/
explore/compaction/title/summary) → `openrouter/z-ai/glm-5.3`;
`DEFAULT_SMALL_MODEL` stays `opencode/nemotron-3-ultra-free`.

Chain rules preserved from BITB-173: **free-first, paid-last** (tier-1 free so
routine failovers cost nothing; paid engages only on double failure), **tier-1
cross-provider** (a provider outage never kills a chain), **paid models ride
OpenRouter only** (`enforce_openrouter_for_paid`). The only rule change: the
*primary* seat itself moves from free to paid on high-stakes lanes.

---

## Functional Requirements

- [x] `.opencode/agents/*.md` frontmatter updated to the matrix above
      (12 agents; mechanical lanes change only their tier-2 hop)
- [x] orchestrator.md prompt updated: "Delegation Reliability" section now
      documents the paid-primary posture instead of claiming all subagent
      primaries are free-tier
- [ ] `scripts/generate-opencode-config.py`: `DEFAULT_MODEL` → GLM-5.3;
      `TIER2_FALLBACK` → `openrouter/deepseek/deepseek-v3.2-exp`; builtin
      chains updated; chain-design comments rewritten for the new posture
- [ ] `scripts/test_generate_opencode_config.py`: chain expectations updated to
      the per-lane matrix (tier-2 is the *other* paid model of the pair);
      `openrouter/openai/gpt-oss-120b` added to `STALE_MODEL_IDS` tripwire;
      global-model test repurposed (GLM-5.3 primary, small_model unchanged)
- [ ] `deployment/kubeopencode/agents.md` model table rewritten to match
      (guarded by `test_models_match_agents_doc`)
- [ ] `opencode.json` regenerated (`make gen-opencode-config`)

## Non-Functional Requirements

- [ ] `make verify-opencode-config` green (valid JSON, 12 agents, every agent
      has fallback_models, fallback routing not silently vanished)
- [ ] `pytest scripts/test_generate_opencode_config.py` green
- [ ] Every model ID in the generated config exists in the live catalog
- [ ] `make pre-commit` passes; no secrets in committed files
- [ ] PR title is a valid conventional commit (squash-merge + release-please)

## Out of Scope

- Swapping the mechanical lanes' mimo primaries (still free, unchanged)
- `small_model` changes (stays `opencode/nemotron-3-ultra-free`)
- Cost telemetry/dashboards for the paid models (candidate follow-up)
- `deepseek-r1-0528` as skeptic primary (kept as a documented swap choice)
