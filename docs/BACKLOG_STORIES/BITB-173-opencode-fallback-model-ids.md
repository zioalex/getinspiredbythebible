# BITB-173: Runtime Fallback Chain Pins Non-Existent Model IDs — Failovers Never Fire

**Status:** ✅ Done
**Priority:** P1
**Size:** S
**Created:** 2026-10-01
**Completed:** 2026-10-01
**PR:** #1130

## User Story

**As** the operator of the KubeOpenCode agent graph, **I want** every `model` and `fallback_models` ID to be a model the provider actually serves, **so that** the runtime-fallback plugin's hops fire when a primary 503s and agents degrade instead of dying mid-dispatch.

## Why This Exists

Surfaced on 2026-10-01 while verifying PRs #1125/#1126: two `verifier` subagent
dispatches died on the primary's `[503] Upstream error from Nvidia`, and the
fallback plugin's recovery attempts both failed with
`ProviderModelNotFoundError`. The chain introduced in #1079 had **never once
fired** because both hop IDs were invalid:

- `opencode/nemotron-3-super-free` — **does not exist on OpenCode Zen.** Zen's
  Nemotron lineup is `nemotron-3-ultra-free` (550B) and `nemotron-3.5-lightning-free`
  (30B-A3B) only. The "Super" variant (Nemotron-3-Super-120B-A12B) is served by
  **OpenRouter**: `openrouter/nvidia/nemotron-3-super-120b-a12b:free`. #1079
  mixed Zen's `opencode/` prefix with OpenRouter's variant naming.
- `openrouter/openai/gpt-oss-120b:free` — **does not exist on OpenRouter.**
  The `:free` suffix is OpenRouter's free-variant marker; gpt-oss-120b has no
  free variant there. The real (paid) ID is `openrouter/openai/gpt-oss-120b`.

The same research pass found a third invalid ID of the same class:
`verse-parity-keeper` and `i18n-qa` had primary `opencode/mimo-v2.5-free`,
which is no longer served by Zen (the catalog has `mimo-v2.6-flash-free`) —
those two agents were dead on every dispatch, with no working fallback to
save them.

Nothing caught any of this because the tests asserted *internal consistency*
(agent .md frontmatter == generated opencode.json == agents.md table), not
*existence*. All three sources agreed on the same wrong IDs.

## The Fix

Corrected chain per the original #1079 intent — **powerful free model first,
paid model last** — with IDs verified against the live gateway catalog
(`opencode models`), the gateway being the source of truth over the docs:

1. **Tier 1 (free)**: `openrouter/nvidia/nemotron-3-super-120b-a12b:free` —
   the free Nemotron-3-Super variant on the provider that actually serves it.
   Different provider from the Zen primary, so it survives a full Zen outage
   (the observed failure mode).
2. **Tier 2 (paid)**: `openrouter/openai/gpt-oss-120b` (~$0.10/$0.40 per 1M) —
   engages only on double failure, bounding cost exposure.
3. **Broken primaries**: `verse-parity-keeper` + `i18n-qa` moved to
   `opencode/mimo-v2.6-flash-free` (the served successor).
4. Files: `scripts/generate-opencode-config.py` (constants renamed
   `TIER1_FALLBACK`/`TIER2_FALLBACK` + rewritten rationale), 12 ×
   `.opencode/agents/*.md`, `scripts/test_generate_opencode_config.py`,
   `deployment/kubeopencode/agents.md` (table + coverage matrix + trade-off
   note), `opencode.json` regenerated via `make gen-opencode-config`.
5. New regression tests: free-first/paid-last ordering, exact chain
   `[tier1, tier2]` per agent, Zen-primary agents must have a cross-provider
   hop, retired-ID tripwire, and `agents.md` table parity extended to both
   fallback columns (the table had been silently wrong since #1079).

## Acceptance Criteria

- [x] No configured model ID is a retired/non-existent ID; every ID appears in `opencode models`
- [x] Tier 1 is free, tier 2 is paid, for every agent (including builtins)
- [x] Every Zen-primary agent has an OpenRouter fallback hop
- [x] `agents.md` table (all three model cells) matches the generated config, enforced by test
- [x] `make gen-opencode-config` + `verify-opencode-config` green; 12 agents present
- [x] `pytest scripts/test_generate_opencode_config.py scripts/test_kubeopencode_manifests.py` green
- [x] `markdownlint` + `yamllint` + `prettier` (pinned) green on touched files

## Out of Scope

- Serving the free Super variant from Zen (impossible — Zen has no Super model; revisit if Zen adds one, which would also restore android-gemini's provider diversity)
- A network-dependent "model exists in catalog" CI check (offline CI can't query the gateway; the retired-ID tripwire + doc/test parity are the offline guards)
- Live-cluster rollout: `make sync-opencode-configmap` + pod restart happen from the operator's workstation after merge (the live ConfigMap still carries the broken IDs until then)

## Verification

```bash
cd <repo-root>
make gen-opencode-config && make verify-opencode-config
python -m pytest scripts/test_generate_opencode_config.py scripts/test_kubeopencode_manifests.py -v
npx markdownlint-cli deployment/kubeopencode/agents.md docs/BACKLOG.md docs/BACKLOG_STORIES/BITB-173-*.md
```
