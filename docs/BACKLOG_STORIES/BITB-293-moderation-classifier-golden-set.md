---
id: BITB-293
status: done
priority: P1
size: M
rank: 190
created: 2026-11-11
prs: [1300]
follow_ups: [BITB-322, BITB-340]
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

- [x] A versioned dataset (e.g. `api/tests/fixtures/safety_golden_set.json`) with crisis, threat and Bible-narrative cases for en, it, de, es, fr, pt, ar, ru, zh, hi, ko. Reuse the existing BITB-186/193/238/239/257 test phrasings where possible. Each case has an expected verdict (block / allow / crisis).
- [x] A runner script (e.g. `scripts/run_safety_golden_set.py --classifier openai_moderation|llama_guard|azure`) calls one provider directly and prints a per-language recall / false-positive table. Exit code is non-zero below configurable thresholds.
- [x] Offline unit tests for the runner and the dataset schema with mocked providers, parametrized across all 11 languages.
- [x] A `workflow_dispatch` workflow (or a mode of `golden-set-live.yml`) that runs it with repo secrets. It is never run on PRs.
- [x] Owner step: run against `omni-moderation-latest` and record per-language results in BITB-288 and here. Decide whether the failover stays enabled for languages that fall below threshold.
- [x] Documented with zero-to-running steps in `docs/HOW-TO-ENABLE-CONTENT-SAFETY.md`.

## Live results (owner-run 2026-11-20)

Run: https://github.com/zioalex/getinspiredbythebible/actions/runs/44774067356 —
`safety-golden-set.yml` (workflow_dispatch, never on PRs), classifier `openai_moderation`
(`omni-moderation-latest`), 132 cases, 0 errors. Thresholds: crisis recall >= 0.90,
threat recall >= 0.90, Bible FP rate <= 0.10, overall and per language.

| Language | Crisis recall | Threat recall | Bible FP rate |
|---|---|---|---|
| en | 25% (1/4) | 100% (4/4) | 0% (0/4) |
| it | 75% (3/4) | 75% (3/4) | 25% (1/4) |
| de | 25% (1/4) | 75% (3/4) | 25% (1/4) |
| es | 75% (3/4) | 75% (3/4) | 25% (1/4) |
| fr | 75% (3/4) | 75% (3/4) | 25% (1/4) |
| pt | 50% (2/4) | 75% (3/4) | 25% (1/4) |
| ar | 50% (2/4) | 75% (3/4) | 25% (1/4) |
| ru | 50% (2/4) | 100% (4/4) | 25% (1/4) |
| zh | 50% (2/4) | 50% (2/4) | 50% (2/4) |
| hi | 50% (2/4) | 50% (2/4) | 0% (0/4) |
| ko | 50% (2/4) | 50% (2/4) | 25% (1/4) |
| overall | 52% (23/44) | 73% (32/44) | 23% (10/44) |

The gate failed globally: every language is below the 0.90 crisis-recall threshold
(`omni-moderation-latest` misses 3 of 4 clear-cut English crisis phrasings), 9 of 11
languages are below the threat threshold (50% for zh/hi/ko), and 9 of 11 exceed the
Bible FP limit (up to 50% for zh). The harness itself behaved correctly — 132/132 cases
scored, 0 errors, and the mismatch pattern is consistent classifier behavior, not a
runner or labeling bug.

**Owner decision (2026-11-21):** the OpenAI Moderation failover rollout (BITB-288) is
**held**. Per BITB-288's own gate ("must pass the multilingual golden set before it is
trusted") the classifier is not trusted at this quality, and with every language below
the crisis threshold there is no per-language subset to keep enabled — the per-language
question is moot. Re-evaluate after BITB-322 (harder cases, revisited thresholds) and
classifier-quality work.

## Out of scope

- Changing classifier thresholds (follow-up once data exists).

## Related

BITB-288, BITB-272, BITB-292, BITB-257, BITB-238.

## Follow-ups

- BITB-322: gray-zone and hate cases, more cases per language, `make` target.
- BITB-340: intermittent `page.test.tsx` teardown race that turned this PR's frontend CI red twice (not caused by this PR).
