# BITB-105: `verse_topics` Is Still Empty in Production — Nothing Runs the Population Script

**Status:** 🚧 In Progress — implementation shipped; AC5 (production rows observed) pending the first
post-merge deploy, see "Post-merge verification" below
**Priority:** P1 — without this, BITB-044 changes nothing in production; the feature stays the exact
silent no-op that story was written to fix
**Size:** M (mostly pipeline wiring, plus one drift check)
**Created:** 2026-08-21
**Prompted by:** PR #970 (BITB-044), which ships `scripts/populate_verse_topics.py` as a manual,
on-demand script with a runbook and no automation

## User Story

**As** the operator, **I want** `verse_topics` to be populated in production automatically and to
stay populated as translations are added, **so that** topic boosting is backed by real data rather
than by a script someone has to remember to run.

## Why This Exists

BITB-044 diagnosed a precise failure: the topic-boosting feature was fully built — query-side
detection, the boosted ranking query, the `verse_topics` table and its indexes — but **nothing ever
inserted a row**, so the `LEFT JOIN` always matched zero and the flag was a no-op even when flipped
on.

PR #970 fixes the *capability* to populate. It does not fix the *fact* of population. Its own
remaining list says so:

> - CI/deploy wiring (e.g. alongside the existing `seed-database` matrix job) — currently a
>   manual/on-demand script.

So on the day #970 merges, production `verse_topics` is still empty and topic boosting is still a
no-op. The gap has moved from "no script exists" to "the script exists and nobody runs it," which
from the database's point of view is the same gap.

This is the same class of failure as **BITB-089**, where a committed Alembic revision matched no path
filter and silently never ran: the artefact is present, correct, and tested, and the system never
executes it. That story's lesson was that "it exists in the repo" and "it has run against
production" are different claims, and only the second one matters.

## Proposed Fix

1. **Run population as part of the deploy/seed path.** `azure-deploy.yml` already has a
   `seed-matrix` → `seed-database` → `seed-database-post` chain that knows which translations exist
   and when they change. Topic population belongs in that chain — most naturally in
   `seed-database-post`, after verses exist. The script is already idempotent
   (`(verse_id, topic_id)` primary key + `ON CONFLICT DO NOTHING`), which is what makes it safe to
   attach to a step that runs more often than strictly necessary.
2. **Re-run when a translation is seeded.** A newly added translation arrives with zero topic rows.
   Whatever triggers seeding for it must also trigger tagging for it, or every new translation
   silently ships without topic boosting — a per-translation repeat of the original bug.
3. **Add a drift/emptiness check that alarms.** The single most valuable artefact here: an assertion
   that, for each seeded translation in a topic-supported language, `verse_topics` is non-empty and
   its coverage is in the expected band (BITB-044 measured 18.3% for KJV, 12.3% for Luther 1912). A
   coverage of zero, or a sudden collapse, is exactly the condition that produced this whole class of
   bug and is invisible from the application's behaviour — search simply returns slightly worse
   results with no error anywhere.
4. **Respect the expand/contract and gating rules BITB-097 just established.** This adds work to the
   deploy path, so it inherits that story's discipline: it must not extend the migration window, and
   a failure here should not be able to take a deploy down — topic rows are an enhancement, not a
   correctness requirement for serving traffic. Decide and document whether a tagging failure is
   fatal to the deploy or merely alarmed; "alarmed, not fatal" is the recommendation, given the
   feature it backs is behind a flag.

## Acceptance Criteria

- [x] `verse_topics` population runs automatically as part of the deploy/seed path, without a human
      remembering the runbook
- [x] A newly seeded translation in a supported language gets topic rows without a separate manual
      step
- [x] A check asserts non-empty `verse_topics` and in-band coverage per supported translation, and
      alarms when it is violated
- [x] A tagging failure's blast radius is decided and documented (recommended: alarm, do not fail the
      deploy)
- [ ] Proven end to end: production `verse_topics` is non-empty for at least KJV and Luther 1912, at
      coverage consistent with BITB-044's measured figures — **open**, see "Post-merge verification"
- [x] `docs/HOW-TO-POPULATE-VERSE-TOPICS.md` updated to describe the automated path, with the manual
      invocation retained for backfills and one-offs

## Decision: blast radius (AC4)

A `verse_topics` tagging failure alarms and does not fail the deploy: topic rows feed only a ranking
boost that is itself behind `topic_boosting_enabled`, so an untagged corpus degrades ranking quality
but never correctness or availability. Both the population and coverage-check steps run
`continue-on-error: true`, violations surface as `::warning::` annotations plus a step-summary table,
and `check_verse_topic_coverage.py` exits 0 on violation unless run with `--strict`.

## Post-merge verification (AC5)

AC5 cannot be satisfied from the implementing branch: it needs a production database the sandbox
cannot reach, and rows only appear once the deploy pipeline actually runs. Ship with the criterion
explicitly open and verify it on the first post-merge deploy:

1. Merge → the `bible_scripts` filter fires on `scripts/populate_verse_topics.py` →
   `seed-database-post` runs both new steps.
2. In that run, read the **Verse Topic Coverage Check** step summary table: `kjv` and `luther1912`
   must be `ok`, at roughly 18.3% / 12.3%.
3. Independent confirmation: `SELECT COUNT(*) FROM verse_topics;` against production, plus the
   per-translation query in `docs/HOW-TO-POPULATE-VERSE-TOPICS.md`.
4. Only then tick AC5 and set this story to Done here and in `docs/BACKLOG.md`.

## Verification

The acceptance criterion that matters is the last measurable one: query production and confirm rows
exist. Everything else in this story is a mechanism for keeping that true, and mechanisms can be
reviewed; the row count cannot be argued with.

The drift check needs a negative rehearsal too — deliberately point it at a translation with no
topic rows and confirm it alarms. An emptiness check that has never been seen to fire is not yet
known to work, and this story exists precisely because an unexercised path stayed broken for months.

## Related

- **BITB-044 / PR #970** — ships the script this story automates
- **BITB-089** — the same failure shape: a correct artefact that nothing executed
- **BITB-097** — deploy-pipeline ordering and gating rules this work must fit inside
- **BITB-104** — cannot produce meaningful numbers until this story puts rows in the database
- `scripts/populate_verse_topics.py`, `.github/workflows/azure-deploy.yml`,
  `docs/HOW-TO-POPULATE-VERSE-TOPICS.md`
