---
id: BITB-365
status: in-review
priority: P2
size: S
created: 2026-11-26
depends_on: [BITB-363]
---

# BITB-365: Mechanical Lanes (i18n-qa, verse-parity-keeper) Run on the Local llama.cpp Server

## User story

As the owner, I want the two mechanical lanes — `i18n-qa` and
`verse-parity-keeper` — to run their per-agent default model on the
privately-hosted llama.cpp server (`llama-cpp/gemma-4-26b`) instead of the
free-tier OpenRouter nemotron, so low-value/high-volume mechanical work stops
burning free-tier API quota and gains a zero-cost, rate-limit-free, private
primary. Heavy lanes (orchestrator/builders/verifier/skeptics) stay untouched
on glm-5.3/deepseek.

## Context

- Owner decision (2026-11-26): llama stays **opt-in globally** — the default
  `model`/`small_model` are unchanged (BITB-363 is correct as-is) — but the
  mechanical lanes get it as their **per-agent default**.
- The provider itself (`provider["llama-cpp"]`, V1 shape) is BITB-363's
  addition; this story consumes it per-agent. This PR therefore **stacks on
  BITB-363's branch** — on bare `main` the generator's
  `enforce_openrouter_for_paid` would reject `llama-cpp/gemma-4-26b` (no
  provider entry) and the config would reference a nonexistent provider.
- Fallbacks stay exactly as they were (`nemotron-3.5-lightning:free`,
  `glm-5.3`): they are the safety net when the local server is unreachable.
  The fallback graph stays OpenRouter-only — no llama fallback hop anywhere
  (a fallback to the local server would tie every lane's resilience to one
  home server).
- The egress path is BITB-362 (PR #1342); the live server already answers
  from the agent pod (HTTP 200 + end-to-end `opencode run` verified).

## What this PR delivers

1. `.opencode/agents/i18n-qa.md` and `.opencode/agents/verse-parity-keeper.md`:
   `model: llama-cpp/gemma-4-26b` (fallbacks untouched; no other agent
   touched). The generated `opencode.json` diff is exactly those two model
   lines.
2. `scripts/generate-opencode-config.py`:
   `enforce_openrouter_for_paid` gains a provider-narrow exemption — the
   self-hosted `llama-cpp` provider serves models on local hardware at zero
   cost, so its non-`:free` id is not billable; any OTHER non-openrouter
   non-free model still fails generation loudly. The chain-design narrative
   is updated for the new mechanical-lane primary.
3. `scripts/test_generate_opencode_config.py`: the BITB-363 opt-in guard
   becomes an **explicit allowlist** — exactly `i18n-qa` and
   `verse-parity-keeper` carry a llama-cpp primary; the global defaults and
   every OTHER agent must still have zero llama references; no fallback hop
   anywhere may reference llama-cpp. Extending the allowlist is a deliberate
   model-policy decision, not a drive-by.
4. `k8s/kubeopencode/agents.md`: the two table rows (test-enforced sync —
   `test_models_match_agents_doc`), the tier-1 narrative, the
   OpenRouter-outage failure-matrix row (mechanical lanes now survive it),
   and the paid-model-convention exemption note.

## Acceptance criteria

- [x] Exactly the two mechanical lanes carry `llama-cpp/gemma-4-26b` as their
      per-agent primary; their fallback chains are byte-identical to before
- [x] Global `model` (`openrouter/z-ai/glm-5.3`) and `small_model` (free
      lightning) unchanged; every other lane unchanged
- [x] Guard updated to the explicit two-lane allowlist; still strict for the
      global default, all other agents, and all fallback chains (29 tests
      green)
- [x] `enforce_openrouter_for_paid` exempts only the zero-cost `llama-cpp`
      provider (provider-narrow), documented in the generator and agents.md
- [x] `make verify-opencode-config`, `make test-opencode-config-live`
      (8/8), `make test-opencode-config-live-selftest`,
      `timeout 1800 make pre-commit` green
- [ ] (Owner step) Pre-merge: from the PR checkout, run the gates and the
      interactive-session check below (the two agents show llama as their
      default and answer)

## Owner pre-merge test (unticked)

```bash
git fetch origin && git checkout origin/feature/llama-mechanical-lanes
make verify-opencode-config
make test-opencode-config-live
make test-opencode-config-live-selftest
timeout 1800 make pre-commit
```

Interactive check that the two lanes really default to the local server
(an `opencode` session in the checkout — the agent picker / session info
shows each agent's default; both must list `llama-cpp/gemma-4-26b`):

```bash
opencode run --agent i18n-qa "Reply with the single word: ping"
opencode run --agent verse-parity-keeper "Reply with the single word: ping"
```

(Both dispatch with the agent's per-agent default — no `--model` override —
and must answer from the local server; if it is unreachable they fall back
to the free lightning hop.)

## Out of scope

- Any global default change (owner ruled: opt-in; BITB-363)
- Any heavy/skeptic lane change; any fallback-chain change
- The netpol egress (BITB-362, PR #1342) and the post-merge promotion
  (BITB-269 sync runbook + pod churn — merge order: #1342, #1343, then this)

## References

- BITB-363 (the provider + the original opt-in guard), BITB-362 (egress),
  BITB-279 (fallback invariants preserved), BITB-236 (the lane matrix this
  edits), BITB-269 (post-merge sync order)
