# BITB-044: Populate `verse_topics` to Activate Topic Boosting

**Status:** 🎯 Todo
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

- [ ] A documented, idempotent population script writes `(verse_id, topic_id)` rows into
      `verse_topics`; safe to re-run.
- [ ] Coverage check: a meaningful share of verses are tagged; the 13 topics each have a
      non-trivial verse set; spot-check accuracy recorded.
- [ ] With `topic_boosting_enabled=True`, topic-laden golden queries improve (or hold)
      Precision@5/MRR; neutral queries do not regress.
- [ ] `topic_boost_factor` chosen against the golden set and documented.
- [ ] Topic boosting enabled in prod.
- [ ] Tests cover the population script and the boosted ranking path.

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
