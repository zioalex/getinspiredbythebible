# BITB-104: Un-stub the `topic_boosted` Eval Config and Measure the Boost

**Status:** 🎯 Todo
**Priority:** P1 — the payoff step; until this runs, topic boosting has never been measured even once
**Size:** S–M (the code change is small; the judgement about enabling is the work)
**Created:** 2026-08-21
**Prompted by:** PR #970 (BITB-044), which deliberately does not tune `topic_boost_factor` or flip
`topic_boosting_enabled`

## User Story

**As** the maintainer, **I want** the eval harness to actually apply topic boosting and report an
A/B against unboosted search, **so that** enabling the flag in production is a decision backed by
numbers rather than the assumption that a feature we built must be helping.

## Why This Exists

`api/search_eval/runner.py` registers a `topic_boosted` config that does nothing:

```python
if config.use_topic_boost:
    logger.warning(
        "topic_boosted eval config is a no-op until BITB-044 populates "
        "verse_topics; falling back to non-boosted search",
        extra={"config": config.name},
    )
```

The registry comment says the same thing: *"``topic_boosted`` is a documented no-op (falls back to
plain hybrid search + a warning) until BITB-044 populates verse_topics — kept here so the CLI can
name it and the report can explain why its numbers equal ``hybrid``'s."*

That was the right call when `verse_topics` was empty. Once BITB-044 lands and BITB-105 puts rows in
production, the stub is the only thing standing between the feature and its first measurement — and
a stub that silently returns the unboosted result while *reporting under a boosted name* is a
dangerous thing to leave lying around. Anyone running `--config topic_boosted` after the data exists
gets a plausible-looking number that is actually the control.

## Proposed Fix

1. **Remove the fallback and apply the boost.** `EvalConfig.use_topic_boost` should drive the same
   boosted ranking path the repository already implements (`api/scripture/repository.py`, the
   `verse_topics` `LEFT JOIN`), with `topic_boost_factor` injectable per-config so a sweep is
   possible without editing settings.
2. **Fail loudly if the data is missing.** If `verse_topics` is empty for the corpus under eval, the
   run must error, not warn-and-continue. The whole failure this story exists to close is a boosted
   config quietly reporting unboosted numbers; replacing one silent fallback with another would miss
   the point.
3. **Run the A/B**: `hybrid` vs `topic_boosted` over the extended golden set from BITB-103, split by
   topic-laden vs neutral, and by language group (corpus-validated / tagged-unvalidated /
   untaggable — see BITB-103's language table, so a flat zero on ru/zh/hi/ko is read correctly).
4. **Sweep `topic_boost_factor`** (default 0.2) across a small range and record the curve rather than
   just the winner — a metric that is flat across the whole range is itself the finding, and would
   mean the boost is not doing meaningful work.
5. **Then decide `topic_boosting_enabled`**, and record the decision and its numbers. "Leave it off"
   is a legitimate outcome of this story; shipping a feature because it exists is not.

## Acceptance Criteria

- [ ] `use_topic_boost` applies real boosting; the no-op warning and fallback are gone
- [ ] An empty `verse_topics` under a boosted config is a hard error, not a warning
- [ ] A/B results recorded for `hybrid` vs `topic_boosted`, broken out by topic-laden vs neutral and
      by the three language groups
- [ ] `topic_boost_factor` swept, the curve documented (not just the chosen value), and the choice
      justified in `docs/SEARCH_EVAL_HOWTO.md`
- [ ] A recorded decision on `topic_boosting_enabled` in prod, with the numbers behind it — including
      the option of leaving it off
- [ ] The registry comment in `runner.py` no longer describes the config as a no-op

## Dependencies

This story is only runnable once both of these hold:

- **BITB-103** — otherwise there is nothing meaningful to measure against (3 topics have no cases at
  all, and there is no neutral control to detect regression)
- **BITB-105** — otherwise `verse_topics` is empty wherever the eval points, and step 2 above turns
  every run into the hard error it should

Running this before either lands produces numbers that look like a result and are not one.

## Verification

The A/B is the deliverable, so the thing worth verifying is that the harness is measuring what it
claims. Before trusting any delta: confirm on a known-tagged verse that the boosted query actually
ranks it differently from the unboosted one. A config that silently no-ops is the exact failure this
story closes, and it would otherwise close it in name only.

## Related

- **BITB-044 / PR #970** — populated `verse_topics`; owns the ACs this story discharges
- **BITB-103** — the golden-set data this consumes
- **BITB-105** — production population, without which the boost stays a no-op in the real system
- **BITB-018** — the parent story that built the boosted ranking path
- `api/search_eval/runner.py`, `api/scripture/repository.py`, `api/config.py`
