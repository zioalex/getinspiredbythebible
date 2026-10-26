# BITB-080 Follow-Ups Enablement Eval — Latency + Quality Measurement

**Date:** 2026-10-25
**Story:** [BITB-080](../BACKLOG_STORIES/BITB-080-suggested-followup-questions.md) — last unticked AC:
*"Perceived end-of-turn latency does not regress measurably (check the stage timings) — measure before flipping the flag on."*
**Eval tooling:** `scripts/run_follow_up_eval.py` (BITB-182) / `make follow-up-eval`

## Recommendation: NEEDS-PROD-RUN (latency: GO, quality: conditional GO)

The latency AC is satisfied by every measurement available in this sandbox — no
measurable regression of the perceived end-of-turn exists, and the mechanism cannot add
meaningful latency by design (in-prompt trailer, no second LLM call). But the sandbox
cannot host the backend, so 33/77 golden-set cases (all `suppressed` scenarios, which
depend on the content-safety pipeline) and the true `chat_stage_timings` A/B could not be
executed. **Do not flip `chat_follow_ups_enabled` in production until the full
`make follow-up-eval` run below passes against a staging/prod-like backend.**

## Setup

- **Sandbox limits (explicit):** no Docker daemon, no PostgreSQL/pgvector, no
  `DATABASE_URL` — `scripts/run_follow_up_eval.py` needs a *running backend*
  (`make docker-up` stack), so the end-to-end run is **not possible here**.
  `OPENROUTER_API_KEY` + egress **are** available, so the LLM-side A/B was real.
- **Eval script health:** `run_follow_up_eval.py --checklist` runs offline (exit 0,
  renders all 77 cases); with no backend it fails gracefully with the documented message
  and **exit code 2**. The script is **not broken** — no code changes were needed.
- **Harness (all production code paths, zero copies):**
  `ChatService._build_messages(follow_ups_enabled=…)` for prompts (the exact thing the
  flag toggles), the real `OpenRouterProvider` with the prod default model
  `meta-llama/llama-3.3-70b-instruct` (config.py:42), prod temperature 0.7 / max_tokens
  1024, real `split_follow_ups()` + `_filter_fabricated_follow_ups()`, and the real
  BITB-182 evaluators (`golden_set/follow_up_evaluators.py`) on real golden-set cases
  from `api/golden_set/test_cases/follow_ups.yaml`.
- Environment: Python 3.12.15, `api/requirements-dev.txt`.

## Methodology

1. **Latency A/B** — 3 questions (en topical / de topical / zh topical, matching the
   "known-slow case" in docs/HOW-TO-READ-CHAT-STAGE-TIMINGS.md) × 3 reps, arms
   interleaved off/on back-to-back (18 streaming calls). Per call: TTFT, time of the
   last *visible* token (before the `<!-- FOLLOWUPS:` trailer), full stream end.
2. **Micro-benchmark** — the only backend CPU the feature adds, on a realistic 5.4 KB
   answer: `split_follow_ups()` + `_filter_fabricated_follow_ups()`.
3. **Quality sample** — 11 turn-1 golden-set cases spanning 7 languages and 3 scenarios
   (+1 multi-turn tap), plus a 15-call trailer-emission probe; outputs judged by the
   automated evaluators **and** a manual read.

## Latency results (flag OFF vs ON)

Interleaved A/B, n=9 pairs; OpenRouter route + answer-length variance dominates
(±10 s), so read the *paired* deltas:

| Metric                     | OFF (mean / median) | ON (mean / median) | Paired delta (mean) |
| -------------------------- | ------------------ | ------------------ | -------------------- |
| TTFT                       | 2664 / 1118 ms      | 1475 / 1236 ms     | **−1190 ms** (noise) |
| Visible answer end (EoT)   | 23738 / 20966 ms    | 16801 / 15632 ms   | **−6936 ms** (noise) |
| Full stream end            | 23738 / 20966 ms    | 17854 / 16184 ms   | −5883 ms             |

- **No measurable regression**: both perceived-latency metrics came out *faster* on the
  flag-on arm (i.e. deltas are within the noise floor; the effect size of the flag
  itself is bounded far below it).
- **The one systematic addition — the trailer tail:** after the visible answer
  finishes, the model streams the `<!-- FOLLOWUPS -->` trailer (mean 146 chars ≈ 36
  tokens) for **mean 1053 ms / median 947 ms (range 552–2183)** before the `completion`
  event fires. In `chat_stage_timings` terms: `ttft` unchanged, `generation` and `total`
  grow by ~1 s, and the chips pop ~1 s after the answer is visibly complete. No text the
  user waits for is delayed.
- **Backend CPU overhead (micro):** `split_follow_ups` 83.5 µs (with trailer) / 1.8 µs
  (without); fabrication filter 78.3 µs (3 chips). **Worst case ≈ 0.16 ms per turn** —
  four orders of magnitude under one LLM token; no new stage is recorded.
- **Prompt cost:** +1115 chars ≈ **+279 input tokens** per eligible turn (~8% of the
  ~14.1k-char system prompt), +~36 output tokens per turn.

## Quality findings (sampled turns, real golden-set cases)

- **10/13 quality-run turns passed every automated check** (count 2–3, ≤120 chars, no
  markup, unique, in-conversation language, no trailer leak, no fabricated refs). All 3
  failures were *chip-count 0* (model emitted no/malformed trailer → silent degradation
  by design, never an error).
- **Chips are concrete, non-generic, in-language, first-person.** Examples: en
  *"Can I forgive someone who doesn't apologize or show remorse?"*; it *"Posso perdonare
  senza dimenticare?"*; de *"Kann ich jemandem vergeben, ohne ihm zu vertrauen?"*; ar
  (RTL) and zh *"罗马书8:28的背景是什么"* (verse-citing case — reference cited in the
  answer, so it survived the fabrication filter).
- **Trailer-emission probe (3 reps × 5 cases):** trailer present 15/15; **≥2 usable
  chips: en 3/3, it 3/3, ko 3/3 — but zh 2/3 and hi 1/3.** The zh/hi misses are the
  model writing *one* compound suggestion instead of 2–3 `|`-separated ones, which the
  sanitizer correctly collapses to "none" per the 2–3-or-none rule.
- **One real quality bug found (manual read):** a ko chip contained a German word —
  *"용서를 praktizieren하는 방법은 무엇인가요?"* — model code-switching that no automated
  check catches. Suggest a per-chip language check or a native-speaker sample review
  for ko before full rollout.
- **Multi-turn:** turn-2 (tapped-chip) returned 0 chips in the single observation —
  same omission failure mode, not a repeat of the tapped question.
- **Not measurable in this sandbox (blocked):** all `suppressed` scenarios (33/77 cases —
  crisis-ml needs the ML safety classifier, off-topic needs the intent classifier) and
  verse grounding (needs scripture DB). Their gates are structurally green in the unit
  suite (`test_compassionate_turn_never_surfaces_follow_ups`,
  `test_off_topic_reply_never_carries_follow_ups`).

## What the full run still needs

1. Backend with Postgres 16 + pgvector + loaded scripture: `make docker-up` (or
   `docker-up-dev`), `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY` set.
2. A/B: run once with `CHAT_FOLLOW_UPS_ENABLED=false`, once with `true`; each time
   `make follow-up-eval` (77 cases) and capture `chat_stage_timings` logs
   (docs/HOW-TO-READ-CHAT-STAGE-TIMINGS.md) to compare `ttft` / `generation` / `total`.
3. Manual read of ~20 sampled outputs per language (esp. ko, zh, hi).

## Risks

- **Cost, not latency:** ~+8% input / +~5% output tokens on every eligible turn.
- **zh/hi chip availability ≈ 60%** with the default model — prompt tweak or
  `LANGUAGE_MODEL_OVERRIDES` may be needed; degradation is silent (by design).
- **Chips appear ~1 s after the answer completes** (completion event) — watch any
  streaming indicator that stays on until `completion`.
- Suppressed-scenario behavior (crisis) is unverified outside unit tests until the live
  run; it depends on the content-safety provider, not on this feature.
