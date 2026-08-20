# BITB-096: Persist the Verse Tsvector in a `verse_tsv` Side Table

**Status:** ✅ Done (2026-08-18) — applied in production, backfilled and verified; query switch landed
**Priority:** P1 (unblocks BITB-095, and removes a migration that will take production down if anyone runs it)
**Size:** M
**Created:** 2026-08-17
**Supersedes:** the generated-column form of `r0004` (BITB-062 / PR #955)

## User Story

**As** the operator of a 2-vCPU/4GB production Postgres, **I want** the migration that took
production down replaced by one that cannot, **and** the hybrid search's per-candidate
`to_tsvector` recomputation eliminated, **so that** `r0004` stops being a landmine without a
repeat of the 2026-08-17 outage.

**The primary justification is safety, not speed.** The merged `r0004` will take production down
if anyone runs `upgrade head`; something has to replace it. The performance gain is real but
narrow, and measured below rather than assumed.

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

Production was at **`r0003`** on the pre-#955 image when this was written, and the merged `r0004`
had never been applied — which is the only reason it could be replaced in place rather than
reverted. It has since landed: `alembic current` reports `r0004 (head)`, and the backfill covers
all 403,856 verses with `bool_and(t.text_tsv = to_tsvector('simple', v.text))` returning true.

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

**Cost accepted:** a primary-key join in the `ts_rank` sites, and a trigger instead of a generated
column's automatic maintenance. The trigger is tested rather than assumed.

## Design

```sql
CREATE TABLE verse_tsv (
    verse_id integer PRIMARY KEY REFERENCES verses(id) ON DELETE CASCADE,
    text_tsv tsvector NOT NULL
);
-- deliberately no index on text_tsv; see "What this is actually worth" below
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
| **`r0004` as implemented here** (whole migration) | **6.3 ms** |
| superseded generated column: `ALTER TABLE` | 7,545 ms |
| superseded generated column: `CREATE INDEX` | 5,337 ms |
| `scripts/backfill_verse_tsv.py`, 403,856 rows | 22 s |
| re-run of a completed backfill | 4.6 s, 0 rows inserted |

The 7.5-second figure is the honest lower bound, not a contradiction of the 33-minute production
run: this fixture is a 61 MB table with no embedding column, on unthrottled hardware. Production
rows carry a 1536-dimension vector, making them roughly 40× wider, on a throttled 2-vCPU server.
The rewrite copies all of it. That ratio is the whole story, and it is why "measured locally" was
never evidence for this class of change.

### What this is actually worth — and where it is a regression

The original framing of this work (BITB-062, BITB-095) claimed the queries "recompute
`to_tsvector('simple', text)` per row". **For `search_verses_text` that was never true.**
`idx_verses_fts_simple` (`scripts/migrations/003`) is an *expression* index, so it already stores
the computed tsvectors and the lookup was always index-backed. Benchmarked on Postgres 16 over
403,856 rows, both indexes freshly built at 10 MB, 2,000 iterations each:

| path | today (expression index) | via `verse_tsv` | delta |
| --- | --- | --- | --- |
| `search_verses_text` (`@@` lookup) | **0.105 ms** | 0.144 ms | **37% slower** |
| `ts_rank` over a 200-row candidate pool (159-char verses) | 2.750 ms | **0.238 ms** | **11.5× faster, −2.51 ms** |

Two conclusions follow, and they reshaped this story:

- **`search_verses_text` keeps using `idx_verses_fts_simple`.** Routing it through the side table
  adds a primary-key hop back into `verses` for work the expression index already does. It is a
  regression, small but real, and there is no reason to take it.
- **`verse_tsv.text_tsv` carries no index.** The only reader is `ts_rank`, which reaches rows by
  `verse_id` from the already-narrowed HNSW pool and uses no index at all. A GIN index here would
  have no reader and would cost write overhead on every seed. Dropping it also removes a trap the
  earlier draft had: an index built on an empty table leaves every backfilled row in the GIN
  *pending list*, which made the planner cost a bitmap scan at 1506 and choose a sequential scan
  (99 ms) until a `VACUUM` merged it. No index, no pending list, no mandatory vacuum.

**So the honest value of this story is:** it removes a migration that will take production down,
and it saves ~2.5 ms per hybrid query — call it 8–12 ms on the throttled 2-vCPU server. Against a
hybrid request that already spends 50–200 ms on an Azure embedding call, that is low single-digit
percent. Worth having; not worth much. The safety argument is what carries it.

## Rollout

Each step is invisible to users, and reversible until step 5.

1. **Preflight** — confirm `alembic current` is `r0003` and production is on `cb245d8`. Hold off
   any `deploy` run: it would push the `text_tsv` image back.
2. **Migrate** — `alembic upgrade head`. Sub-second; the sanctioned path is re-running the
   `run-migrations` job (`api/alembic/README.md` forbids pointing Alembic at production from a
   local machine).
3. **Backfill** — `python scripts/backfill_verse_tsv.py`. Resumable, holds no lock anyone waits
   on, ends with `ANALYZE verse_tsv` for planner statistics. Slow on the throttled server; it
   does not matter, because nothing waits on it.
4. **Verify** — `SELECT count(*) FROM verses` equals `SELECT count(*) FROM verse_tsv`, and
   `bool_and(t.text_tsv = to_tsvector('simple', v.text))` is true.
5. **Only then** switch the queries — BITB-095 Phase 1, reworked (below).
6. ~~Retire `idx_verses_fts_simple`~~ — **cancelled.** `search_verses_text` still uses it, and
   measurably should. See BITB-095 below.

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
      `--dry-run`, ending in `ANALYZE verse_tsv`
- [x] Integration tests: the trigger populates on insert, follows an update to `text`, the stored
      value equals `to_tsvector('simple', text)` exactly, `text_tsv` carries **no** index, the
      FK cascades
- [x] Verified end to end against a real Postgres 16 at 403,856 rows: upgrade, backfill,
      resume-after-interruption, parity, downgrade, and re-upgrade
- [x] Applied in production (2026-08-18): `alembic current` reports `r0004 (head)`,
      `count(verses) = count(verse_tsv) = 403,856`, and
      `bool_and(t.text_tsv = to_tsvector('simple', v.text))` returns true
- [x] Query switch landed: `ts_rank` in `search_verses_hybrid` and
      `search_verses_hybrid_boosted` reads `verse_tsv` via `LEFT JOIN`;
      `search_verses_text` deliberately untouched
- [x] Benchmarked rather than assumed: the FTS lookup is *slower* through the side table, so
      `search_verses_text` is left on `idx_verses_fts_simple` and BITB-095 Phase 2 is cancelled

## Follow-ups this creates

**PR #1000 is superseded, not merged.** It switched three call sites to a `text_tsv` *column*
that does not exist in this design. The correct switch — two sites, not three — is included in
this story's own change instead, so #1000 should be closed.

**BITB-095 Phase 2 is cancelled.** It planned to drop `idx_verses_fts_simple` on the grounds that
nothing would use it after the switch. `search_verses_text` still does, and measurably should
(0.105 ms against 0.144 ms through the side table). The index stays.

**Naming correction.** BITB-095 and the first draft of this story both referred to
`search_verses_hybrid_multi`. No such function exists — the second `ts_rank` site is in
`search_verses_hybrid_boosted`. The multi-embedding case is a parameter (`extra_embeddings`) of
`search_verses_hybrid`, not a separate method. The right two sites were changed regardless, since
they were found by grepping for `ts_rank` over `verses`.

**The pipeline failures remain unaddressed and rank above everything here.** None is a schema
change, and between them they caused the outage and hid it:

- `deploy` runs before `run-migrations`, so new code is live before its migration.
- `functional-tests` needs only `deploy`, so it races the migration and reports failures it
  cannot avoid.
- A CI job timeout kills the client but not server-side DDL, which then holds its lock with no
  possible commit.
- `azure-deploy.yml` has **no `push` trigger** for `main`; it fires on `workflow_run` after
  "CI/CD - Test Application". A merge touching only paths that workflow ignores (e.g. a
  `deployment/**`-only change) therefore never deploys — observed with #1002 on 2026-08-18.
- The `production` environment approval gate had 16 runs queued behind it, the oldest from
  11 August. A gate with a two-week backlog is not gating anything.

## Related

- BITB-062 / PR #955 — the parent story and the migration this supersedes
- BITB-095 — the query switch that consumes this, and the expression-index retirement
- BITB-089 — why the pipeline runs Alembic, and the `deploy → run-migrations` order
- `scripts/migrations/003_add_fulltext_index.sql` — where `idx_verses_fts_simple` came from
- `api/alembic/versions/r0004_add_verse_tsv_side_table.py`, `scripts/backfill_verse_tsv.py`
