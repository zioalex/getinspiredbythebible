---
id: BITB-293
status: todo
priority: P1
size: M
rank: 190
created: 2026-11-11
---

# BITB-293: 11-Language Safety Golden Set for a Single Moderation Classifier (OpenAI Moderation First)

**Prompted by:** BITB-288 (#1280). Its AC 2, a live golden set against `omni-moderation-latest`, could not be done because no harness can score a single classifier.

## Problem

BITB-288 wires `OPENAI_API_KEY` into production so the BITB-272 `ml_only` failover to OpenAI
Moderation (`api/providers/openai_moderation.py`, `OpenAIModerationProvider`) actually runs. The
story also requires the failover classifier to pass the multilingual safety golden set before it
is trusted. The only golden-set harness (`scripts/run_golden_set.py` +
`.github/workflows/golden-set-live.yml`) drives the chat API end to end and scores answers. It
cannot target one classifier, so nobody can measure:

- crisis recall (self-harm) per language,
- threat / directed-harm recall per language,
- the false-positive rate on Bible narrative ("Why did Cain kill Abel?", BITB-257) per language.

The same question applies to Llama Guard and to the Azure Content Safety failover (BITB-292).

## Acceptance criteria

- [ ] A versioned dataset (e.g. `api/tests/fixtures/safety_golden_set.json`) with crisis, threat and Bible-narrative cases for en, it, de, es, fr, pt, ar, ru, zh, hi, ko. Reuse the existing BITB-186/193/238/239/257 test phrasings where possible. Each case has an expected verdict (block / allow / crisis).
- [ ] A runner script (e.g. `scripts/run_safety_golden_set.py --classifier openai_moderation|llama_guard|azure`) calls one provider directly and prints a per-language recall / false-positive table. Exit code is non-zero below configurable thresholds.
- [ ] Offline unit tests for the runner and the dataset schema with mocked providers, parametrized across all 11 languages.
- [ ] A `workflow_dispatch` workflow (or a mode of `golden-set-live.yml`) that runs it with repo secrets. It is never run on PRs.
- [ ] Owner step: run against `omni-moderation-latest` and record per-language results in BITB-288 and here. Decide whether the failover stays enabled for languages that fall below threshold.
- [ ] Documented with zero-to-running steps in `docs/HOW-TO-ENABLE-CONTENT-SAFETY.md`.

## Out of scope

- Changing classifier thresholds (follow-up once data exists).

## Related

BITB-288, BITB-272, BITB-292, BITB-257, BITB-238.
