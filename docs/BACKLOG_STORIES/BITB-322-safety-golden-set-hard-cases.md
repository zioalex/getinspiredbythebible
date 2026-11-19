---
id: BITB-322
status: todo
priority: P2
size: S
rank: 195
created: 2026-11-16
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

- [ ] At least 8 cases per language and category, adding gray-zone threats, indirect crisis phrasings
      and graphic Bible passages in all 11 languages (en, it, de, es, fr, pt, ar, ru, zh, hi, ko)
- [ ] A `hate` category (expected `block`) with recall reported by the runner
- [ ] `make safety-golden-set CLASSIFIER=…` target, with the make-target audit regenerated
- [ ] Thresholds revisited using the owner's first BITB-293 live results

## Related

BITB-293, BITB-288, BITB-292, BITB-294.
