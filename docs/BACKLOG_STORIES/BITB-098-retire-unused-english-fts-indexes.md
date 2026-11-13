# BITB-098: Retire the Two English FTS Indexes Nothing Queries

**Status:** 🎯 Todo
**Priority:** P3 — pure waste, but bounded and not urgent
**Size:** S (one revision; the care is in the evidence and the lock, not the code)
**Created:** 2026-08-18
**Prompted by:** BITB-095's adjacent finding, confirmed while closing BITB-096

## User Story

**As** the operator of a 2-vCPU/4GB production Postgres, **I want** the GIN indexes that no query
reads to stop being maintained on every write, **so that** seeding and any future backfill are not
paying to update index structures nothing will ever scan.

## The Finding

`scripts/migrations/003_add_fulltext_index.sql` created four GIN indexes:

| index | table | reader |
| --- | --- | --- |
| `idx_verses_fts_simple` | `verses` | `search_verses_text` — **keep, see below** |
| `idx_passages_fts_simple` | `passages` | `search_passages_hybrid` — keep |
| `idx_verses_fts_english` | `verses` | **none** |
| `idx_passages_fts_english` | `passages` | **none** |

Grepping the repository for `to_tsvector('english', …)` returns exactly two hits: the two
`CREATE INDEX` statements that define these indexes. No Python, no SQL, no migration, and no
script ever builds an `english` tsvector, so no query can match either index's expression.

They have been maintained on every insert and update since 2026, over 403,856 verses and the
passages table, for no reader at all.

## ⚠️ `idx_verses_fts_simple` must not be dropped

This story is narrowly about the two `_english` indexes. Dropping `idx_verses_fts_simple` was
BITB-095 Phase 2, and it is **cancelled**: `search_verses_text` still matches
`to_tsvector('simple', text) @@ …` against it, and measured over 403,856 rows that is *faster*
than routing the lookup through `verse_tsv` (0.105 ms against 0.144 ms). See BITB-096 for the
benchmark. Anyone reading "retire the unused FTS indexes" and reaching for the `simple` ones has
misread this story.

## Evidence Required Before Dropping Anything

A grep proves nothing in *this repository* reads them. It does not prove nothing ever has —
`psql` sessions, ad-hoc reporting, or a tool outside the repo would not show up. Get the
database's own answer first:

```sql
SELECT indexrelname,
       idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE indexrelname LIKE 'idx_%fts_%'
ORDER BY idx_scan;
```

`idx_scan = 0` on both `_english` indexes is the case made. Note the counter resets on
`pg_stat_reset()` and on a server rebuild, so also record how long the server has been collecting:

```sql
SELECT stats_reset FROM pg_stat_database WHERE datname = current_database();
```

A zero scan count over two days means much less than one over two months.

## Implementation

A new revision (`r0005`):

```python
with op.get_context().autocommit_block():
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_verses_fts_english")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_passages_fts_english")
```

`CONCURRENTLY` is not optional. A plain `DROP INDEX` takes `ACCESS EXCLUSIVE` on `verses`, and a
request for that lock queues **every** reader behind it — the mechanism that turned a slow
migration into a total outage on 2026-08-17 (BITB-096). `CONCURRENTLY` cannot run inside a
transaction, hence `autocommit_block()`; this is the pattern `api/alembic/README.md` documents.

Set `lock_timeout` as `r0004` does, so the drop fails fast rather than queueing.

`downgrade()` recreates both, also `CONCURRENTLY`. Recreating them is slow (a full GIN build over
403,856 rows) but the downgrade path has to be honest about what it restores.

## Acceptance Criteria

- [ ] `pg_stat_user_indexes.idx_scan` captured from production for all four FTS indexes, with
      `stats_reset` alongside it, and pasted into the PR
- [ ] `r0005` drops **only** `idx_verses_fts_english` and `idx_passages_fts_english`
- [ ] `DROP INDEX CONCURRENTLY` inside an `autocommit_block()`, with `lock_timeout` set
- [ ] `downgrade()` recreates both, also `CONCURRENTLY`
- [ ] `idx_verses_fts_simple` and `idx_passages_fts_simple` untouched, and a comment in the
      revision says why
- [ ] Index sizes recorded before and after, so the saving is a number rather than a claim

## Related

- BITB-096 — where this was confirmed; also why the `simple` index stays
- BITB-095 — raised it as an adjacent finding and declined to act on a grep alone
- BITB-018 — quotes the `idx_verses_fts_english` definition, the only other mention in the docs
- `scripts/migrations/003_add_fulltext_index.sql`
