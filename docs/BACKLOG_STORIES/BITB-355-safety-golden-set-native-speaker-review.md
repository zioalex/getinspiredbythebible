---
id: BITB-355
status: todo
priority: P2
size: S
created: 2026-11-21
depends_on: [BITB-322]
---

# BITB-355: Safety Golden Set — Native-Speaker Review of the 200 New Non-English Cases

**Prompted by:** BITB-322 follow-ups (PR #1325). The expanded dataset was authored by an AI session
with no native-speaker review.

## Problem

BITB-354's evaluation and every future rollout gate read their numbers from
`api/tests/fixtures/safety_golden_set.json`. BITB-322 added 220 cases to it; 200 of those are
non-English (20 per language for it, de, es, fr, pt, ar, ru, zh, hi, ko: the indirect-crisis,
conditional-threat and graphic-Bible cases with ids 05-08 plus the new `hate` category ids 01-08).
They are machine-authored translations. No fluent speaker has checked any of them.

The dataset is a measurement instrument: every recall and false-positive number is only as
trustworthy as the labels. An unnatural phrasing (one a native speaker would never produce), a
register or dialect mismatch, or a translation that shifts the meaning can silently flip what a
case actually tests — a threat case that reads harmless inflates the miss count; a
Bible-narrative case that reads as a personal attack inflates false positives. Neither result says
anything about the classifier. `api/tests/test_safety_golden_set.py` enforces schema, unique ids,
native script and minimum counts offline, but no test can judge naturalness.

## Acceptance criteria

- [ ] One fluent speaker per language (it, de, es, fr, pt, ar, ru, zh, hi, ko) reviews that
      language's 20 new texts in the fixture for (a) naturalness — would a real user write or say
      this — and (b) meaning fidelity to the intended case type (crisis / threat / hate /
      bible_narrative) and its expected verdict.
- [ ] Corrections land as in-place fixture text edits keeping the same ids (renumber only a case
      replaced entirely), with `cd api && python -m pytest tests/test_safety_golden_set.py -q`
      green.
- [ ] The review outcome recorded per language in this story (language, reviewer date, edits made),
      so gate decisions taken on the set cite a reviewed dataset.

## Out of scope

- The 132 clear-cut cases shipped by BITB-293 (labelled reuses of existing test phrasings), unless a
  reviewer flags one.
- The 20 new English cases (authored alongside them; flag in review if something reads wrong).

## Related

BITB-322, BITB-293, BITB-354, BITB-288.
