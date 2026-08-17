# BITB-095: Switch the Verse FTS Queries to `text_tsv` and Retire the Expression Index

**Status:** 🚧 In Progress — Phase 1 (query switch) implemented; Phase 2 (index drop) not started
**Priority:** P2
**Size:** S (two phases, each small; the care is in the ordering, not the code)
**Created:** 2026-08-17
**Depends on:** BITB-062 / PR #955 — `r0004` must be **deployed and applied in production**, not merely merged

## User Story

**As** the operator of a 2-vCPU/4GB production Postgres, **I want** the verse full-text queries to
read the persisted `verses.text_tsv` column instead of recomputing `to_tsvector('simple', text)`
per row, **so that** the column PR #955 paid for actually gets used and the redundant expression
index can be dropped instead of being maintained on every write forever.

## Why This Exists as Its Own Story

PR #955 was deliberately additive. It adds

```sql
verses.text_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
CREATE INDEX idx_verses_text_tsv ON verses USING GIN (text_tsv)
```

and changes **no** query. So on the day #955 deploys, production carries two GIN indexes over the
same value — `idx_verses_fts_simple` (the expression index from `scripts/migrations/003`, which the
queries still use) and `idx_verses_text_tsv` (which nothing uses yet) — plus a stored column on
403,856 rows. That is the intended intermediate state, not a mistake: it is what makes the switch
reversible. This story is the other half, and closing it is what turns #955 from a cost into a win.

### The ordering hazard that forced the split

`.github/workflows/azure-deploy.yml` runs `deploy` **before** `run-migrations`:

```
deploy → run-migrations
```

New application code is therefore live for the length of a migration run before the migration it
depends on has been applied. Ship the query switch in the same PR as the column and every public
search request in that window returns 500 — `column "text_tsv" does not exist`. Splitting the work
is the entire mitigation, and the same asymmetry constrains this story too:

| | safe direction | unsafe direction |
| --- | --- | --- |
| **add** column/index, then switch query | column exists before the query needs it | — |
| **switch** query, then drop old index | old index survives a rollback to old code | dropping first leaves old code on a seq scan over 403k rows |

Hence two phases, in two separate deploys.

## Phase 1 — Point the queries at the column (no DDL)

Three call sites in `api/scripture/repository.py` compute `to_tsvector('simple', v.text)` at query
time against `verses`:

| line | function | expression |
| --- | --- | --- |
| ~257 | `search_verses_text` | `to_tsvector('simple', text) @@ plainto_tsquery('simple', :query)` |
| ~403 | `search_verses_hybrid` | `ts_rank(to_tsvector('simple', v.text), ...)` |
| ~615 | `search_verses_hybrid_multi` | `ts_rank(to_tsvector('simple', v.text), ...)` |

All three become `text_tsv` / `v.text_tsv`.

**Only the first one is an index question.** `search_verses_text`'s `@@` is the predicate the
planner resolves through a GIN index, and after this change it resolves through
`idx_verses_text_tsv` rather than `idx_verses_fts_simple`. The two `ts_rank` sites run over the
already-narrowed candidate pool (a few hundred rows from the HNSW CTE) and use no index either way;
switching them saves recomputing the tsvector per candidate row, which is a modest win, but the
real reason to include them is that **Phase 2 cannot be justified while any query still names the
old expression.** Leave one behind and dropping `idx_verses_fts_simple` becomes a guess.

`to_tsvector('simple', p.text)` at ~line 815 queries `passages`, which has no generated column.
Out of scope, and `idx_passages_fts_simple` stays.

Results are **identical by construction**: the generated column's expression is character-for-character
the expression the index and the queries use. This is a plan change, not a semantics change.

## Phase 2 — Drop `idx_verses_fts_simple` (separate PR, separate deploy)

A new revision (`r0005`) doing `DROP INDEX CONCURRENTLY IF EXISTS idx_verses_fts_simple`.

**Do not fold this into Phase 1.** Between the two, the old index is what makes a rollback to the
previous application version survivable — that code still matches the expression, and without the
index it does a sequential scan over the whole `verses` table on every public search. The gap
should be at least one deploy cycle with Phase 1 confirmed healthy in production.

Use `CONCURRENTLY`: a plain `DROP INDEX` takes `ACCESS EXCLUSIVE` on `verses` and will queue behind
(and then block) every reader. Same `autocommit_block()` pattern `r0004` uses, for the same reason.

### Adjacent finding — not this story

`idx_verses_fts_english` and `idx_passages_fts_english` (also `scripts/migrations/003`) are queried
by **nothing**. No code anywhere in the repository builds a `to_tsvector('english', ...)`. They are
two GIN indexes maintained on every insert and update for no reader at all. That is worth its own
story with its own evidence — `pg_stat_user_indexes.idx_scan` from production — rather than being
smuggled into this one on the strength of a grep.

## Acceptance Criteria

### Phase 1

- [x] `search_verses_text` matches `text_tsv @@ plainto_tsquery('simple', :query)`
- [x] Both `search_verses_hybrid` / `_multi` `ts_rank` sites read `v.text_tsv`
- [x] No `to_tsvector('simple', ...)` over `verses` remains anywhere in `api/`
- [x] `test_uses_tsvector_match_not_ilike` updated — it asserted the literal string `to_tsvector`
      appears in the compiled SQL, which this change removes. It now asserts the new form **and
      that the old expression is absent**, which is the half that licenses Phase 2
- [x] An integration test asserts the switched query returns exactly the rows the old expression
      form returns, running both against the same seeded database
- [ ] **Not** asserted in tests: that the query is index-backed. The integration fixture seeds a
      handful of rows, where Postgres correctly prefers a sequential scan over any GIN index, so a
      plan assertion there would test the fixture's size rather than the production plan. The
      `EXPLAIN` evidence is a Phase 2 criterion, gathered against production
- [ ] Merged only after `r0004` is confirmed applied in production (`alembic current` reports
      `r0004`), not merely after #955 merges

### Phase 2

- [ ] `r0005` drops `idx_verses_fts_simple` with `CONCURRENTLY` inside an `autocommit_block()`
- [ ] Downgrade recreates it (also `CONCURRENTLY`)
- [ ] Opened only after Phase 1 has been running in production through at least one deploy cycle
- [ ] `EXPLAIN` from production, before and after, in the PR — proving the surviving plan uses
      `idx_verses_text_tsv`

## Related

- BITB-062 — the parent story; this closes its last deferred item
- PR #955 — adds the column and index this consumes
- BITB-089 — why the deploy pipeline runs Alembic at all, and the `deploy → run-migrations` order
  that dictates the phasing
- `scripts/migrations/003_add_fulltext_index.sql` — where `idx_verses_fts_simple` came from
- `api/alembic/versions/r0004_add_verses_text_tsv.py`, `api/scripture/repository.py`
