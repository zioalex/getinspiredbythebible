---
id: BITB-363
status: in-review
priority: P2
size: S
created: 2026-11-26
prs: [1343]
follow_ups: [BITB-364]
---

# BITB-363: llama.cpp Server as an Opt-In opencode Provider in the Generated Config

## User story

As the owner, I want the repo's generated opencode config to carry the
privately-hosted llama.cpp server (OpenAI-compatible endpoint, model
`llama-cpp/gemma-4-26b`) as a provider, so agents can select the self-hosted
model explicitly — and so the committed config can be tested before merge
instead of living only in the pod's workspace layer.

## Context

- The provider currently exists ONLY in this pod's workspace layer
  (`/workspace/opencode.json`, outside the repo): the committed/generated
  `opencode.json` has no llama provider. The workspace shape is validated
  live on opencode 1.18.31 (V1 config: singular top-level `provider`).
- The egress path is opened by the supplemental netpol `agent-egress-llama`
  (BITB-362, PR #1342 — separate concern, separate PR).
- Live validation already done by the owner from the workspace config: HTTP
  200 from the agent pod to the server's `/v1/models`, and an end-to-end
  `opencode run` against the model.
- Opt-in by design: the global defaults (`openrouter/z-ai/glm-5.3` primary,
  free lightning `small_model`) and every fallback chain are untouched — the
  BITB-279 invariants (OpenRouter-only fallback graph, free tier-1) survive
  unchanged. A self-hosted free model in a fallback chain would tie every
  agent's resilience to one home server; it stays a deliberate per-session
  choice.

## What this PR delivers

1. `scripts/generate-opencode-config.py`: the `llama-cpp` provider entry in
   the exact V1 shape of the live-validated reference (api
   `openai-compatible`, `llama.cpp Server`, baseURL
   `http://<llama-host>:8080/v1`, `apiKey: dummy`, all three timeouts
   `false`, one `gemma-4-26b` model with its GGUF id and
   `context 32768 / output 8192` limits). The host is committed in the
   generator (the reproducible source) and the generated `opencode.json` —
   the same single-home rule as the BITB-362 netpol manifest, and nowhere
   else.
2. Regenerated `opencode.json`: a 21-line provider block and **zero other
   drift**; the generated `provider["llama-cpp"]` subtree is byte-identical
   to the live reference (canonicalized jq comparison).
3. Tests (`scripts/test_generate_opencode_config.py`, 27 → 29):
   `test_llama_cpp_provider_v1_shape` pins the V1 shape — the baseURL as a
   host-agnostic pattern (`http://<ipv4>:8080/v1`), so the test never
   hardcodes the address — and `test_llama_cpp_is_opt_in_only` is the
   regression guard: global `model`/`small_model` unchanged and zero
   `llama-cpp/` references in any agent's model or fallback selection.

## Acceptance criteria

- [x] Generated `opencode.json` carries `provider["llama-cpp"]` byte-identical
      to the live-validated workspace reference; no drift beyond the block
- [x] V1 shape test + opt-in regression test in the generator suite (29 green)
- [x] Global `model` and `small_model` unchanged; no agent model/fallback
      references llama-cpp (enforced by test, not by review vigilance)
- [x] `make verify-opencode-config` green (valid JSON, 12 agents, fallbacks,
      plugin)
- [x] `make test-opencode-config-live` green (8/8 assertion groups, including
      the scratch-boot plugin-load check and a noop subagent dispatch on the
      committed config) and `make test-opencode-config-live-selftest` green
- [x] `timeout 1800 make pre-commit` green
- [ ] (Owner step) Pre-merge end-to-end from the PR checkout: re-run the four
      gates plus `opencode run --model llama-cpp/gemma-4-26b` — the exact
      commands below

## Owner pre-merge test (unticked)

From the PR checkout (workstation or the pod's own shell — the live gates
boot a scratch opencode, never the live server):

```bash
git fetch origin && git checkout origin/feature/llama-cpp-provider-config
make verify-opencode-config
make test-opencode-config-live
make test-opencode-config-live-selftest
timeout 1800 make pre-commit
opencode run --model llama-cpp/gemma-4-26b "Reply with the single word: ping"
```

The last command is the end-to-end probe: it selects the opt-in provider and
expects a reply. (The in-pod workspace config already answers this; this run
proves the *committed* config does too.)

## Out of scope

- Any default-model change or fallback-chain hop to llama-cpp (BITB-279
  invariants; would be its own story with its own incident analysis)
- The post-merge promotion: `make sync-opencode-configmap` (BITB-269 sync
  runbook — merge first, then sync, then pod churn) is the owner's follow-up,
  NOT part of this PR
- k8s/ or deployment/ doc updates (the netpol PR #1342 owns that lane)

## Follow-ups

- **BITB-364** — the pre-push git hook fails on new-branch pushes: it
  falls back to all files, its write-mode hooks (prettier×2, markdownlint
  --fix) rewrote ten unrelated files in this session's tree, and yamllint
  then failed on prettier's own reflowed lines. Observed live while pushing
  this branch; filed with the reproduction and the rewrite list.

## References

- BITB-362 (the egress allow this provider rides on), BITB-269 (config-sync
  runbook: merge before sync), BITB-279 (fallback invariants preserved),
  BITB-280 (the live-config gate this PR ran), BITB-236 (the paid-primaries
  matrix the defaults belong to)
- Live reference shape: this pod's `/workspace/opencode.json`
  `provider["llama-cpp"]` (validated on opencode 1.18.31)
