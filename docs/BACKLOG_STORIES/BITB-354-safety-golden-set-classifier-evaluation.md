---
id: BITB-354
status: todo
priority: P1
size: M
created: 2026-11-21
depends_on: [BITB-322]
---

# BITB-354: Safety Golden Set — Evaluate Llama Guard and Azure Content Safety Against the Expanded Set

**Prompted by:** BITB-322 follow-ups (PR #1325). The recalibrated golden-set gates and the expanded
352-case dataset shipped, but only one classifier has ever been measured, and it cannot pass any
gate.

## Problem

BITB-322 recalibrated the safety-golden-set gates from the owner's first live
`omni-moderation-latest` run (2026-11-20, run 44774067356, the old 132-case set): crisis recall
>= 0.75, threat recall >= 0.75, hate recall >= 0.75, Bible false-positive rate <= 0.25, overall AND
per language. That measured classifier sits far below every gate (crisis recall 52% overall,
25-75% per language), so the owner held the BITB-288 OpenAI Moderation failover rollout (owner
decision 2026-11-21): the classifier is not trusted at that quality, in any language.

The runner (`scripts/run_safety_golden_set.py`, also `make safety-golden-set CLASSIFIER=…`) already
supports two classifiers that nobody has measured against any version of the set:

- `llama_guard` — OpenRouter; BITB-321 (open PR #1313) fixed its tolerance for null primary content,
- `azure` — Azure Content Safety; BITB-294 (open PR #1323) provisions the resource and wires the
  failover hop, off by default.

Until one classifier demonstrably passes the recalibrated gates, the content-safety failover design
(BITB-272/288/292) has no trusted classifier to fail over to, and every rollout decision stays
provisional. Gates are only meaningful against a classifier that can plausibly meet them.

## Acceptance criteria

- [ ] Owner step: run the Safety Golden Set workflow_dispatch (paid APIs, owner-only, never on
      PRs) for `llama_guard` and `azure` against the expanded 352-case set; record the per-language
      results (crisis / threat / hate recall, Bible FP rate, errors) in this story and in
      BITB-288/BITB-293.
- [ ] A decision recorded here: which classifier (if any) passes the recalibrated gates overall AND
      per language, and what is next for the ones that do not (prompt or threshold tuning,
      replacement, or a further recalibration story with recorded reasoning).
- [ ] The BITB-288 failover rollout decision revisited in writing from that data.

## Out of scope

- Changing the dataset or the thresholds again (a further recalibration needs its own recorded
  reasoning, per the BITB-322 precedent).
- New classifier providers (the runner's three are enough for this evaluation).

## Related

BITB-322, BITB-293, BITB-288, BITB-292, BITB-294, BITB-321.
