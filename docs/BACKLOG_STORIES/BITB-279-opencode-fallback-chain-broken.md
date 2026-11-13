---
id: BITB-279
status: in-progress
priority: P1
size: S
rank: 100
created: 2026-11-08
---

# BITB-279: Broken Fallback Chains — `opencode/*` Model References Never Serve; Paid Tier-2 Cannot Rescue an Exhausted Key

**Status note:** chains, generator constants, test suite and agents.md guards aligned in this PR; BITB-280 live-load gate follows
**Size note:** (agents) + S follow-up (generator constants)
**Incident:** 2026-11-08 21:30–21:36 UTC (fallback chain dead during weekly-key exhaustion)

## Bug Report (live evidence, 2026-11-08)

The OpenRouter weekly key limit hit ($20.01 of $20.00) at ~21:30 UTC. Every
paid-primary call then failed with `AI_APICallError: Key limit exceeded`, and
the runtime-fallback plugin's chains could not recover:

- **Tier-1 fallbacks were dead on arrival.** All 10 `mode: subagent` agents
  (and the global `small_model`) referenced `opencode/nemotron-3-ultra-free`
  — the opencode Zen gateway, for which this pod has **no credentials**
  (the generated config's `provider.opencode` block carries only timeout
  options). Live log 21:34:39: replay dispatched on
  `opencode/nemotron-3-ultra-free` → `session.idle detected silent model
  failure (no first token received)`.
- **Tier-2 fallbacks were paid models on the same exhausted key**
  (`openrouter/deepseek/deepseek-v3.2-exp`, `openrouter/z-ai/glm-5.3`) —
  no `:free` variant of deepseek-v3.2-exp exists on OpenRouter.
- Net effect 21:34:40: `Max fallback attempts reached (2)` →
  `no more fallback models available`. Every dispatch lane was down until
  the user manually switched the orchestrator session to
  `~z-ai/glm-latest` at 21:36.
- The mechanical lanes (i18n-qa, verse-parity-keeper) were also running on
  dead primaries (`opencode/mimo-v2.6-flash-free`) and only worked by
  silently falling to their first fallback on every dispatch.

Free models on OpenRouter draw no credit, so a **valid `:free` tier-1 makes
the chain immune to key exhaustion**. At audit time the free slate is 12
models, all `nvidia/nemotron-*:free` variants
(`nemotron-3-ultra-550b-a55b:free` — the proven workhorse — plus
`nemotron-3.5-lightning:free`, `nemotron-3.5-super-vl:free`,
`nemotron-3-nano-omni-30b-a3b-reasoning:free`).

## Requirements

### Fixed in this PR (agent definitions + regenerated config)

1. Every agent's tier-1 fallback: `opencode/nemotron-3-ultra-free` →
   `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (10 agents).
2. Mechanical lanes' primaries: `opencode/mimo-v2.6-flash-free` →
   `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (free by design,
   BITB-236); their first fallback de-duplicated to
   `openrouter/nvidia/nemotron-3.5-lightning:free`.
3. Paid tier-2 fallbacks stay (glm-5.3 / deepseek-v3.2-exp): they cannot
   rescue key exhaustion but remain the right defense for free-model rate
   caps and upstream 5xx/429 outages — different failure mode, different tier.

### Follow-up in this story (needs `scripts/` changes — dispatched separately)

4. `scripts/generate-opencode-config.py` constants still reference the dead
   Zen gateway: `DEFAULT_SMALL_MODEL` and `ZEN_FREE_FALLBACK` =
   `opencode/nemotron-3-ultra-free`, `MIMO_FREE` =
   `opencode/mimo-v2.6-flash-free`; built-in agents (build/plan/general/
   explore/compaction/title/summary) inherit these. Until fixed, the
   regenerated `opencode.json` keeps a broken `small_model`. The follow-up
   also adds the BITB-280 live-load gate (CI boots a scratch opencode
   instance with the committed config and asserts zero `failed to load
   plugin` + subagent `question: deny`) so a config that cannot serve in
   the real runtime can never merge again.

## Acceptance Criteria

- [x] All agent `fallback_models` tier-1 = a verified-existing
      `openrouter/:free` model; no `opencode/*` reference remains in any
      agent definition
- [x] Mechanical lanes' primaries are free-tier and their fallback lists
      contain no duplicates of the primary
- [x] `make gen-opencode-config` + `make verify-opencode-config` pass;
      generator test suite passes; regenerated `opencode.json` committed
- [x] Generator constants (`DEFAULT_SMALL_MODEL`, `ZEN_FREE_FALLBACK`,
      `MIMO_FREE`, builtin fallbacks) fixed — same PR, second commit;
      suite + agents.md now enforce the free-tier tier-1 invariant
      (cross-provider rule retired: OpenRouter is the only credentialed
      provider and the only free slate)
- [ ] BITB-280 live-load gate added to CI — follow-up dispatch
- [ ] (owner) after merge + sync + pod restart: with the key still
      exhausted, a fullstack-engineer dispatch completes on the free
      tier-1 (runtime log shows the fallback commit to
      `nvidia/nemotron-3-ultra-550b-a55b:free`, no silent-failure line)

## Out of Scope

- Adding more free providers/lineages (the free slate is what it is;
  revisit when OpenRouter adds non-nemotron free models)
- Changing the paid model posture (BITB-236) — primaries stay paid
  (glm-5.3 / deepseek-v3.2-exp)

## References

- Live log: `/tmp/.local/share/opencode/log/opencode.log` 21:30–21:36 UTC
  (Key-limit errors; `session.idle silent model failure` on
  `opencode/nemotron-3-ultra-free`; `Max fallback attempts reached (2)`)
- Fallback plugin log: `/tmp/.config/opencode/opencode-fallback.log`
  (`Planned fallback … -> opencode/nemotron-3-ultra-free (will be attempt 2)`
  → silent failure → manual model change at 21:36:29)
- OpenRouter model audit 2026-11-08: `z-ai/glm-5.3` OK,
  `deepseek/deepseek-v3.2-exp` OK (paid, no `:free`),
  `nvidia/nemotron-3-ultra-550b-a55b:free` OK,
  `nvidia/nemotron-3.5-lightning:free` OK,
  `opencode/*` not servable in this pod
- BITB-236 (model posture), BITB-269 (plugin/registry work), BITB-270/271
  (follow-up stories), BITB-280 (live-load gate, follow-up)
