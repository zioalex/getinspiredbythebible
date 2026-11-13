# BITB-044: Populate `verse_topics` to Activate Topic Boosting

**Status:** 🚧 In Progress — keyword-based population shipped; LLM tagging,
golden-set tuning, and prod enablement remain (see "Delivered / Remaining" below)
**Priority:** P2 (Medium) — unblocks the third Phase-1 lever; currently a silent no-op
**Size:** M (1-2 days)
**Created:** 2026-06-07

## User Story

As a user, I want verses about my detected theme (anxiety, forgiveness, grief, …) to
rank higher, so that the most pastorally relevant verses surface first — and as the
maintainer I want the topic-boosting feature we already built to actually do something.

## Problem

Topic boosting was implemented under **BITB-018**: query-side topic detection exists
(`api/chat/topics.py`, `TOPIC_KEYWORD_MAP`), the ranking applies a boost, and the
repository `LEFT JOIN`s a `verse_topics` table (`api/scripture/repository.py:~409, ~540`).
Migration `004_add_topic_boosting_schema.sql` creates `verse_topics` and its indexes.

**But nothing ever populates `verse_topics`** — there is no `INSERT` into it anywhere in
the codebase. The table is empty, so the join returns no rows and the boost multiplies by
zero matches. Enabling `topic_boosting_enabled` today would have **no effect**. This story
fills that data gap.

## Approach

1. **Define the tag source of truth** — reuse the 13 topics already encoded in
   `api/chat/topics.py` (anxiety, peace, forgiveness, anger, loneliness, trust, fear,
   hope, love, grief, guidance, patience, joy). Confirm they match the `topics` table.
2. **Tag verses → topics** for the corpus (~31k verses/translation). Recommended:
   LLM-assisted tagging (each verse → 0..N topics) with a human-spot-check pass;
   keyword-map seeding from `TOPIC_KEYWORD_MAP` can bootstrap obvious matches cheaply.
   Tagging can be done once on a canonical translation and shared by verse identity if
   appropriate, or per-translation — decide and document.
3. **Persist** as a repeatable, idempotent script under `scripts/` (e.g.
   `scripts/populate_verse_topics.py`) that upserts into `verse_topics` and can be
   re-run as topics evolve. (Note: no `INSERT`/seed currently exists.)
4. **Validate** with the golden eval set from **BITB-043**: enabling
   `topic_boosting_enabled` should improve ranking on topic-laden queries without
   regressing neutral ones; tune `topic_boost_factor` (default 0.2).
5. **Enable** `topic_boosting_enabled` in prod once validated.

## Acceptance Criteria

- [x] A documented, idempotent population script writes `(verse_id, topic_id)` rows into
      `verse_topics`; safe to re-run. — `scripts/populate_verse_topics.py`
- [x] Coverage check: a meaningful share of verses are tagged; the 13 topics each have a
      non-trivial verse set; spot-check accuracy recorded. — see "Delivered" below
- [ ] With `topic_boosting_enabled=True`, topic-laden golden queries improve (or hold)
      Precision@5/MRR; neutral queries do not regress.
- [ ] `topic_boost_factor` chosen against the golden set and documented.
- [ ] Topic boosting enabled in prod.
- [x] Tests cover the population script — `api/tests/test_populate_verse_topics.py`,
      `api/tests/test_topic_tagging.py`. Boosted-ranking-path tests already existed
      (BITB-018); not modified by this pass.

## Delivered / Remaining

**Delivered (this pass):**

- `api/chat/topic_tagging.py` — corpus-side matcher, word-boundary + bounded-suffix
  matching, per-language (a keyword from one language's list cannot match text tagged
  with a different language).
- `api/chat/topics.py` restructured so the keyword map is language-segmented
  (`TOPIC_KEYWORDS_BY_LANGUAGE`), with `TOPIC_KEYWORD_MAP` derived from it — the query-side
  `detect_topics()` API is unchanged.
- `scripts/populate_verse_topics.py` — idempotent, `--dry-run`/`--replace`/`--translation`/
  `--verbose`, keyword-seeded population. Run against the real KJV and Luther 1912 corpora
  during development (see `docs/HOW-TO-POPULATE-VERSE-TOPICS.md`): 18.3% of KJV verses and
  12.3% of Luther 1912 verses tagged, no topic above ~3.2% coverage.
- Deliberately does **not** flip `topic_boosting_enabled` or tune `topic_boost_factor`.

**Remaining (follow-up stories/passes):**

- LLM-assisted tagging pass to catch thematic matches with no literal keyword overlap
  (composable with the keyword-seeded rows via `ON CONFLICT DO NOTHING`).
- Validate against the BITB-043 golden eval set; un-stub the `topic_boosted` config warning
  in `api/search_eval/runner.py`.
- Tune and document `topic_boost_factor`; enable `topic_boosting_enabled` in prod.
- Run `--dry-run --verbose` for `it`/`es`/`fr`/`pt`/`ar` against real corpus data and extend
  `CORPUS_KEYWORD_DENYLIST` if any topic exceeds the 25% guideline (only validated for
  `en`/`de` so far — no local corpus data for the others in this environment).
- CI/deploy wiring (e.g. alongside the existing `seed-database` matrix job) — currently a
  manual/on-demand script.

## Files / Config

| Item | Location |
|---|---|
| Topics + keyword map | `api/chat/topics.py` (`TOPIC_KEYWORD_MAP`) |
| Schema (already present) | `scripts/migrations/004_add_topic_boosting_schema.sql` |
| Join usage | `api/scripture/repository.py:~409, ~540` |
| Flag / factor | `api/config.py` (`topic_boosting_enabled`, `topic_boost_factor`) |
| New population script | `scripts/populate_verse_topics.py` *(to create)* |

## Related

- **BITB-018** — parent story
- **BITB-043** — depends on its golden eval set for validation; enable topic boosting
  after both this data work and BITB-043 are done
- `docs/EMBEDDINGS_IMPROVEMENT_STRATEGY.md` — §1.3 Topic-Based Boosting
