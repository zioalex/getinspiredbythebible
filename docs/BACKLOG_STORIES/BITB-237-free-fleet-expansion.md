# BITB-237: Free-Fleet Expansion — Pre-Gate Verifier for Nemotron, Family-Matched Tier-1 Failovers

**Priority:** P2 (Medium)
**Status:** 🎯 Todo (blocked by PR #1202 merge — same files)
**Size:** M
**Created:** 2026-10-24

---

## Background

BITB-236 (PR #1202) moved high-stakes lanes to paid primaries with the free
tier demoted to tier-1 rescue hops. Two consequences motivate this follow-up:

1. **The free tier's workload collapses to near-zero in the happy path.** With
   reliable paid primaries, tier-1 hops rarely fire, so free models (which the
   owner wants carrying real work) sit idle. The owner explicitly asked for
   Nemotron to take more workload and for other free models to act actively.
2. **Failovers drop quality more than necessary.** A GLM-5.3 primary failing
   over to Nemotron (unbenchmarked on every public coding leaderboard — checked
   against the live Aider Polyglot on 2026-10-24) is a blind quality jump. The
   Zen gateway serves free variants of the *same families* as our paid
   primaries: `opencode/glm-5.3-flash-free` and `opencode/deepseek-v4.1-flash-free`
   — both live-catalog verified 2026-10-24.

Also carried here: a doc-truth fix found during BITB-236 research — the
generator comment calls the 550B "rank #4 overall", conflating OpenRouter's
*usage* rank (2.57T tokens/week) with a quality ranking. The 550B has no
published coding benchmark.

---

## User Story

**As a** developer running the Plan → Build → Verify relay,
**I want** a free-model pre-gate in front of the paid verifier and family-matched
free failovers behind every paid primary,
**so that** trivially-red rounds cost nothing to catch, every failover keeps
near-primary quality, and the free tier carries real workload instead of idling.

---

## Functional Requirements

### 1. Pre-gate verifier (new 13th agent)

- [ ] New agent `pre-verifier` (`.opencode/agents/pre-verifier.md`):
      mode subagent, primary `opencode/nemotron-3-ultra-free` (Nemotron's new
      active seat, per owner), tier-1
      `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (cross-provider free
      hop), tier-2 `openrouter/z-ai/glm-5.3`; `permission: edit deny`, bash
      allow-list limited to lint / typecheck / fast-test commands (mirror the
      verifier permission block).
- [ ] Runs lint (Ruff/Black/ESLint), typecheck (MyPy/tsc), and the fast test
      suites BEFORE any paid `verifier` dispatch in the Verify stage.
- [ ] Fail-open semantics: inconclusive or unavailable gate → proceed straight
      to the paid verifier. The gate saves money; it never blocks the relay.
- [ ] Trivially-red gate → bounce a fix brief straight back to the builder
      without spending the paid DeepSeek skeptic (AGENTS.md's "Haiku is only
      for cheap pre-gating" pattern, finally given a seat in this graph).
- [ ] Orchestrator routing table + Verify-stage prose updated to describe the
      two-step verify (pre-gate → paid skeptic).
- [ ] Agent-count invariants updated: `make verify-opencode-config` hardcodes
      "expected 12 agents"; the generator test file and Makefile check must be
      bumped to 13 (or derived from the agents directory) — and the doc table
      in `deployment/kubeopencode/agents.md` gains the row.

### 2. Family-matched tier-1 failover hops

- [ ] Workhorse lane (orchestrator + 5 builders): tier-1
      `opencode/nemotron-3-ultra-free` → `opencode/glm-5.3-flash-free`
      (same family as the GLM-5.3 primary — near-primary quality on failover).
- [ ] Skeptic lane (verifier + 3 auditors): tier-1 →
      `opencode/deepseek-v4.1-flash-free` (deepseek family).
- [ ] Builtins: tier-1 → `opencode/glm-5.3-flash-free` (they inherit the GLM
      primary).
- [ ] Mechanical lanes unchanged (mimo primary, openrouter-nemotron:free
      tier-1, GLM tier-2); `small_model` unchanged.
- [ ] Chain rules preserved (BITB-173): tier-1 free + cross-provider (Zen hop
      behind an OpenRouter primary), tier-2 paid = the other pair member.
- [ ] All 12 `.md` frontmatters + generator chain-design comments + test
      expectations + `deployment/kubeopencode/agents.md` + regenerated
      `opencode.json` updated together (the BITB-236 lesson: these move as
      one unit guarded by the same tests).

### 3. Usage-rank comment truth fix

- [ ] `scripts/generate-opencode-config.py`: the "rank #4 overall, #1 free"
      comment on the 550B must say *usage* rank explicitly and note the model
      is absent from published coding leaderboards (verified 2026-10-24).

## Non-Functional Requirements

- [ ] Every new model ID verified against the live catalog (`opencode models`)
      before commit — gateway, not docs, is the source of truth (BITB-173).
- [ ] `pytest scripts/test_generate_opencode_config.py` and
      `pytest scripts/test_kubeopencode_manifests.py` green;
      `make verify-opencode-config` green.
- [ ] `make pre-commit` passes; no secrets; conventional commits; PR title
      conventional (squash-merge + release-please).

## Out of Scope

- Mimo mechanical-lane primaries (owner confirmed keep)
- `small_model` changes
- `deepseek-r1-0528` as skeptic primary
- Cost telemetry/dashboards for paid-model spend

## Dependency

**Blocked by PR #1202 merge.** This story edits the same files (frontmatters,
generator, tests, deployment doc, opencode.json) — branch from post-merge
main, never stack on the open PR.
