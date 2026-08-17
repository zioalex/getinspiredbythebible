# BITB-096: Persist the Verse Tsvector in a `verse_tsv` Side Table

**Status:** 🚧 In Progress — migration, model, backfill and tests implemented; not yet applied to production
**Priority:** P1 (unblocks BITB-095, and removes a migration that will take production down if anyone runs it)
**Size:** M
**Created:** 2026-08-17
**Supersedes:** the generated-column form of `r0004` (BITB-062 / PR #955)

## User Story

**As** the operator of a 2-vCPU/4GB production Postgres, **I want** the persisted verse tsvector to
land without rewriting the `verses` table, **so that** BITB-095 can stop recomputing
`to_tsvector('simple', text)` per row without a repeat of the 2026-08-17 outage.

## Why This Exists — the 2026-08-17 outage

PR #955 merged `r0004`:

```sql
ALTER TABLE verses ADD COLUMN text_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
```

Production was down for roughly 45 minutes on the deploy. Four things went wrong, and each one
is a constraint on the replacement:

1. **A `STORED` generated column forces a full table rewrite under `ACCESS EXCLUSIVE`.** Every
   read and write of `verses` blocks for the duration. On ~400k production rows the rewrite was
   still running at 33 minutes.
2. **The `ADD COLUMN` was not the only coupling.** `r0004` also put `text_tsv` on the `Verse` ORM
   model, and `search_verses_text` issues `select(Verse)` — which emits every mapped column. So
   *every verse read* began referencing a column that only existed after the migration. The
   pipeline runs `deploy` **before** `run-migrations` (BITB-089), so the new image was live and
   failing on every request before the migration had even started.
3. **A CI timeout does not stop a migration.** `run-migrations` hit `timeout-minutes: 30` and the
   job died. That killed the *client*, not the server-side DDL. The orphaned `ALTER TABLE` held
   its lock for another 15 minutes, working toward a `COMMIT` that could never arrive — Alembic,
   the only thing that would have sent it, no longer existed. Recovery required
   `pg_cancel_backend()` on the leader pid, then rolling the image back to `cb245d8`.
4. **The estimate in the migration was wrong by three orders of magnitude.** Its docstring said
   "low single-digit seconds -- measured". That measurement was not taken at production scale or
   on production hardware.

Production is currently at **`r0003`** on the pre-#955 image. The merged `r0004` has never been
applied, which is the only reason it can be replaced in place rather than reverted.

### Why a side table, and not the other three options

| approach | rewrite of `verses` | HNSW rebuild | downtime |
| --- | --- | --- | --- |
| generated column (`r0004` as merged) | yes | no | **hard outage, unbounded** |
| shadow table + `RENAME` | no | **yes — 403,856 × 1536-dim** | ~0 at swap, hours of CPU saturation |
| batched `UPDATE` + trigger | no | no, but every row rewritten → **HNSW churn and bloat** | none, lasting index damage |
| **`verse_tsv` side table** | **no** | **no** | **none** |

`verses` carries `idx_verse_embedding_hnsw` over 1536-dimension vectors in production (see
`api/alembic/README.md` invariant 2). Anything that rewrites rows pays for that index again —
which is what rules out the shadow-table copy and the batched `UPDATE`, both of which are the
textbook zero-downtime answers and both of which are wrong *here*. Writing tsvectors into a
separate table touches none of it.

The side table also breaks coupling **2** permanently: with no tsvector on the `Verse` model,
`select(Verse)` no longer depends on the migration having run. New application code stays
compatible with an un-migrated database, which is the property whose absence turned a slow
migration into a total outage.

**Cost accepted:** a primary-key join in the FTS queries, and a trigger instead of a generated
column's automatic maintenance. The trigger is tested rather than assumed.

## Design

```sql
CREATE TABLE verse_tsv (
    verse_id integer PRIMARY KEY REFERENCES verses(id) ON DELETE CASCADE,
    text_tsv tsvector NOT NULL
);
CREATE INDEX idx_verse_tsv_tsv ON verse_tsv USING GIN (text_tsv);
```

maintained by an `AFTER INSERT OR UPDATE OF text` trigger on `verses`. Deletes need no handling —
`ON DELETE CASCADE` covers them. `verses` takes no writes at runtime (nothing in `api/` inserts,
updates or deletes a `Verse`), but the seeding scripts do, so the trigger is what keeps the table
correct without anyone remembering to re-run the backfill.

Every statement in the migration runs against an **empty** table, so the whole revision is catalog
work. `SET LOCAL lock_timeout = '5s'` and `SET LOCAL statement_timeout = '10min'` bound it **from
inside the database**, which is the direct lesson of failure 3: the harness's timeout bounded
nothing.

Bulk population is deliberately *not* in the migration — see `scripts/backfill_verse_tsv.py`.
Filling 400k rows is data movement, not schema work, and it has no business inside a transaction
or inside a job with a 30-minute guillotine.

### Measurements

Postgres 16, 403,856 rows, identical data, local hardware:

| | time |
| --- | --- |
| **`r0004` as implemented here** (whole migration) | **12 ms** |
| superseded generated column: `ALTER TABLE` | 7,545 ms |
| superseded generated column: `CREATE INDEX` | 5,337 ms |
| `scripts/backfill_verse_tsv.py`, 403,856 rows | 22 s |
| re-run of a completed backfill | 4.6 s, 0 rows inserted |

The 7.5-second figure is the honest lower bound, not a contradiction of the 33-minute production
run: this fixture is a 61 MB table with no embedding column, on unthrottled hardware. Production
rows carry a 1536-dimension vector, making them roughly 40× wider, on a throttled 2-vCPU server.
The rewrite copies all of it. That ratio is the whole story, and it is why "measured locally" was
never evidence for this class of change.

### `VACUUM` after the backfill is mandatory, not hygiene

The GIN index is created on an empty table, so every row the backfill inserts lands in the index's
**pending list** (`fastupdate` is on by default) rather than the index proper. Measured at 403,856
rows:

| | estimated cost of the bitmap index scan | plan chosen | query time |
| --- | --- | --- | --- |
| before `VACUUM` | 1506 | **sequential scan** | 99 ms |
| after `VACUUM ANALYZE verse_tsv` | 27 | bitmap index scan | 0.1 ms |

Without the vacuum the planner rejects the index and the entire point of the story evaporates
silently — the query still returns correct rows, just slowly. `scripts/backfill_verse_tsv.py`
therefore runs `VACUUM ANALYZE verse_tsv` as its final step, and it is not optional.

## Rollout

Each step is invisible to users, and reversible until step 5.

1. **Preflight** — confirm `alembic current` is `r0003` and production is on `cb245d8`. Hold off
   any `deploy` run: it would push the `text_tsv` image back.
2. **Migrate** — `alembic upgrade head`. Sub-second; the sanctioned path is re-running the
   `run-migrations` job (`api/alembic/README.md` forbids pointing Alembic at production from a
   local machine).
3. **Backfill** — `python scripts/backfill_verse_tsv.py`. Resumable, holds no lock anyone waits
   on, ends with the mandatory `VACUUM ANALYZE`. Slow on the throttled server; it does not matter.
4. **Verify** — `SELECT count(*) FROM verses` equals `SELECT count(*) FROM verse_tsv`, and
   `bool_and(t.text_tsv = to_tsvector('simple', v.text))` is true.
5. **Only then** switch the queries — BITB-095 Phase 1, reworked (below).
6. **Later, separate deploy** — retire `idx_verses_fts_simple`, BITB-095 Phase 2, unchanged.

## Acceptance Criteria

- [x] `r0004` rewritten in place — production is at `r0003`, so leaving the generated-column
      version in the chain means `upgrade head` still runs the outage
- [x] The migration drops a stale `verses.text_tsv` if present, so a dev/CI database already
      stamped at the superseded `r0004` converges on the same schema (`DROP COLUMN` is
      metadata-only, so this is instant even on 400k rows)
- [x] `SET LOCAL lock_timeout` / `statement_timeout` inside the migration
- [x] `VerseTsv` ORM model, so `env.py`'s `_OWNED_TABLES` picks it up and `alembic check` stays
      clean; **no** tsvector column on `Verse` and no `relationship()` between them
- [x] `scripts/backfill_verse_tsv.py` — batched, per-batch commits, resumable, idempotent,
      `--dry-run`, ending in `VACUUM ANALYZE`
- [x] Integration tests: the trigger populates on insert, follows an update to `text`, the stored
      value equals `to_tsvector('simple', text)` exactly, the GIN index exists, the FK cascades
- [x] Verified end to end against a real Postgres 16 at 403,856 rows: upgrade, backfill,
      resume-after-interruption, parity, downgrade, and re-upgrade
- [ ] Applied in production; `alembic current` reports `r0004` and counts match
- [ ] `EXPLAIN` from production showing `idx_verse_tsv_tsv` in the plan (BITB-095 Phase 2 criterion)

## Follow-ups this creates

**PR #1000 must be reworked, not merged.** It switches three call sites in
`api/scripture/repository.py` to a `text_tsv` *column* that will no longer exist:

- `search_verses_text` — inner-join `verse_tsv`, match
  `verse_tsv.text_tsv @@ plainto_tsquery('simple', :query)`
- `search_verses_hybrid` and `search_verses_hybrid_multi` —
  `LEFT JOIN verse_tsv vt ON vt.verse_id = d.id`, with
  `ts_rank(COALESCE(vt.text_tsv, ''::tsvector), ...)`. **Left** join and `COALESCE` deliberately:
  a verse missing its row ranks zero instead of vanishing from results.

Its merge gate changes from "`r0004` applied" to "backfill verified complete".

**The pipeline failures are their own story, and rank above this one.** None is a schema change,
and all three caused the outage: `deploy` runs before `run-migrations`; `functional-tests` needs
only `deploy`, so it races the migration and reports failures it cannot avoid; and a CI job
timeout orphans server-side DDL rather than stopping it.

## Related

- BITB-062 / PR #955 — the parent story and the migration this supersedes
- BITB-095 — the query switch that consumes this, and the expression-index retirement
- BITB-089 — why the pipeline runs Alembic, and the `deploy → run-migrations` order
- `scripts/migrations/003_add_fulltext_index.sql` — where `idx_verses_fts_simple` came from
- `api/alembic/versions/r0004_add_verse_tsv_side_table.py`, `scripts/backfill_verse_tsv.py`
