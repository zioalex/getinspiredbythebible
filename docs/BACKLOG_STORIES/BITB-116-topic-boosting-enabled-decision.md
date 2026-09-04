# BITB-116: Decide `topic_boosting_enabled` From the BITB-104 A/B Numbers

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S (reading a report and flipping a flag — the numbers are the work, not the code)
**Created:** 2026-09-01
**Prompted by:** BITB-104, which builds the harness this decision needs but cannot run it here

## User Story

**As** the maintainer, **I want** a recorded decision on `topic_boosting_enabled` backed by real
A/B and factor-sweep numbers, **so that** topic boosting ships (or stays off) on evidence instead
of the assumption that a feature we built must be helping.

## Why This Exists

BITB-104 un-stubbed the `topic_boosted` eval config so it actually runs `search_hybrid_boosted()`
against real `verse_topics` data instead of silently falling back to `hybrid`'s numbers — and, in
the process, found and fixed a real bug: `topic_boost_factor` was being multiplied against a
`COUNT()` (bigint) column with no other numeric context in the query, so Postgres's untyped-
parameter resolution inferred a `bigint` bind type and asyncpg silently truncated every factor
between 0 and 1 (including the 0.2 default) to `0` — meaning the boost was a complete no-op even
before BITB-044's stub, confirmed by an integration test against real Postgres+asyncpg.

That harness fix landed the *capability* to measure the boost. It could not produce the
*measurement*: `--run` needs `DATABASE_URL` pointed at a corpus with real `verse_topics` rows plus
Azure embedding credentials, which a sandboxed dev environment does not have. `docs/SEARCH_EVAL_HOWTO.md`
already documents this as a standing limitation for the harness in general — BITB-104 doesn't change
that, it just makes the eventual numbers trustworthy once they arrive.

## What This Story Delivers

1. Trigger **Actions → Search Eval — Full → Run workflow** with `configs: hybrid,topic_boosted`
   against `eval-prod` (the only route with populated `verse_topics`).
2. Sweep `topic_boost_factor` (the workflow's `topic_boost_factor` input, e.g.
   `0.0,0.1,0.2,0.4,0.8`) and record the full curve in `docs/SEARCH_EVAL_HOWTO.md`'s
   "topic_boost_factor sweep results" table — not just the winning value. A metric that is flat
   across the whole range is itself the finding.
3. Read the results broken out by topic-laden vs. neutral cases and by the three language groups
   from BITB-103 (corpus-validated / tagged-unvalidated / untaggable) — a flat `ru/zh/hi/ko` delta
   means "not taggable", not "boosting doesn't help".
4. Decide `topic_boosting_enabled` (`api/config.py`) and record the decision with its numbers.
   **"Leave it off" is a legitimate outcome of this story; shipping a feature because it exists is
   not.** Flipping the flag is a deploy change (Terraform/app settings), not just a code change —
   file that as its own PR once the decision is made.

## Acceptance Criteria

- [ ] `eval-prod` run completed with `configs: hybrid,topic_boosted` and a `topic_boost_factor`
      sweep
- [ ] The sweep curve is recorded in `docs/SEARCH_EVAL_HOWTO.md`, replacing the "pending" table
- [ ] A written decision on `topic_boosting_enabled`, with the numbers behind it, including the
      option of leaving it off
- [ ] If the decision is "enable": a follow-up PR flips the flag in `api/config.py` and/or
      Terraform and deploys it

## Dependencies

- **BITB-104** (must be merged first — this story only makes sense once the harness measures the
  real boosted path)

## Related

- **BITB-104** — un-stubbed the eval config and fixed the truncation bug this decision's numbers
  depend on
- **BITB-103** — golden-set topic labels and language-group table this reads results through
- **BITB-044 / PR #970** — populated `verse_topics`, the data this measures
