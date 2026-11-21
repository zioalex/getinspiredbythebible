---
id: BITB-322
status: in-review
priority: P2
size: S
rank: 195
created: 2026-11-16
prs: [1325]
follow_ups: [BITB-354, BITB-355, BITB-356]
depends_on: [BITB-293]
---

# BITB-322: Safety Golden Set — Gray-Zone Cases and a `make` Target

**Prompted by:** BITB-293 follow-ups. The first dataset
(`api/tests/fixtures/safety_golden_set.json`) has 4 crisis, 4 threat and 4 Bible-narrative cases per
language: clear-cut phrasings that measure a baseline. It does not yet test the cases most likely to
split classifiers.

## Problem

- **Too few hard cases.** There are no gray-zone threats (conditional or veiled: "someone should teach
  him a lesson"), no hate cases, no Bible passages with graphic violence (Judges 19, 2 Kings 2:23-24,
  the Psalm 137:9 imprecation) and no indirect crisis phrasings ("everyone would be better off without
  me"). With only 4 cases per language and category, one miss moves recall by 25 points.
- **No `make` entry point.** The runner is `python scripts/run_safety_golden_set.py`. Adding a
  `make safety-golden-set` target requires regenerating `scripts/make_target_audit.json` /
  `docs/MAKE_TARGET_AUDIT.md`, and that audit is already stale on `main` (`test_report_is_current`
  fails), so BITB-293 did not add one.

## Acceptance criteria

- [x] At least 8 cases per language and category, adding gray-zone threats, indirect crisis phrasings
      and graphic Bible passages in all 11 languages (en, it, de, es, fr, pt, ar, ru, zh, hi, ko)
- [x] A `hate` category (expected `block`) with recall reported by the runner
- [x] `make safety-golden-set CLASSIFIER=…` target, with the make-target audit regenerated
- [x] Thresholds revisited using the owner's first BITB-293 live results
- [ ] Owner step: re-run the Safety Golden Set workflow_dispatch (paid API, owner-only) against the
      expanded 352-case set, record the results here (and in BITB-288), and ratify — or adjust — the
      0.75 / 0.75 / 0.75 / 0.25 defaults. The BITB-288 failover rollout stays **held** (owner
      decision 2026-11-21) until a live run meets the gates overall AND per language.

## Thresholds (recalibrated 2026-11-21)

The original 0.9 / 0.9 / 0.1 runner defaults were set with zero live data. The owner's first live
`omni-moderation-latest` run (2026-11-20, run 44774067356, then 132 clear-cut cases; table in the
BITB-293 story) measured crisis recall **52%** overall (25-75% per language), threat recall **73%**
(50-100%) and Bible FP **23%** (9 of 11 languages above 0.10): no language met the 0.90 crisis gate,
so the gate could not discriminate "improving" from "stuck". With 8 cases per category per language,
one miss moves a rate by 12.5 points, so the recalibrated defaults (in the runner, the workflow's
`workflow_dispatch` input defaults, and `docs/HOW-TO-ENABLE-CONTENT-SAFETY.md`) mean "at most 2
misses of 8 per language" (`0.75`) and "at most 2 wrong blocks of 8 Bible questions" (`0.25`), plus
the new `--min-hate-recall 0.75`. They still fail the currently-measured classifier quality
everywhere and are reachable by a meaningfully better one; the owner ratifies them via the next live
run.

## Related

BITB-293, BITB-288, BITB-292, BITB-294.

## Follow-ups

- BITB-354: evaluate Llama Guard (BITB-321 context) and Azure Content Safety (BITB-294 / PR #1323)
  against the expanded 352-case set to find a classifier that can pass the recalibrated gates —
  the only measured classifier (`omni-moderation-latest`) cannot, and the BITB-288 rollout stays
  held.
- BITB-355: native-speaker review of the 200 new machine-authored non-English fixture texts
  (20 per language) before the set gates any rollout decision.
- BITB-356: once PR #1302 (BITB-325) and this PR have both merged, re-run the make-target audit
  regeneration and confirm `make test-makefile` is fully green on `main`.
