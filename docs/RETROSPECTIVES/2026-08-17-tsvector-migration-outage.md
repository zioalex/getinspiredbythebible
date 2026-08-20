# Retrospective: the tsvector Migration Outage (2026-08-17/18)

**Impact:** production fully down ~45 minutes (2026-08-17, ~20:53–21:40 UTC); permanent disk
doubling 32→64 GB; one Terraform wedge blocking all applies; ~36 hours of remediation work.
**Trigger:** PR #955 deployed Alembic `r0004` — a `STORED` generated tsvector column on `verses`.
**Resolution:** `pg_cancel_backend()` on orphaned DDL, image rollback, redesign as the `verse_tsv`
side table (BITB-096), reapplied cleanly, query switch landed (#1003).

## Timeline (condensed)

| when (UTC) | event |
| --- | --- |
| 08-17 20:10 | #955 merges: `ALTER TABLE verses ADD COLUMN text_tsv ... GENERATED ... STORED` |
| 20:52 | `deploy` puts the new image live — code referencing a column that doesn't exist yet |
| 20:53 | `functional-tests` runs anyway: 33 failures. **Production down** — every verse read 500s |
| 20:53–21:04 | `run-migrations` sits unapproved behind the `production` gate |
| 21:05 | Migration approved; table rewrite begins under `ACCESS EXCLUSIVE` |
| 21:35 | `timeout-minutes: 30` kills the *runner*. The server-side `ALTER TABLE` keeps its lock, working toward a `COMMIT` no client can send |
| ~21:38 | Operator finds the orphan via `pg_stat_activity`, `pg_cancel_backend()`, rolls image back to `cb245d8`. **Production up** |
| 08-18 | Auto-grow (triggered by the rewrite's table copy + WAL) wedges Terraform: config says 32 GB, disk is 64 GB, Azure forbids shrink. Fixed via `ignore_changes` (#1002) — which then **never deployed**, exposing the missing trigger path |
| 08-18 | `r0004` rewritten in place as the `verse_tsv` side table; applied in 6.3 ms-class catalog work; 403,856 rows backfilled, parity verified; query switch merged green (#1003) |

## Root causes — five, all independent

1. **Wrong migration shape.** `STORED` generated column = full table rewrite under
   `ACCESS EXCLUSIVE`. On the throttled 2-vCPU server, 33+ minutes of blocking every read/write.
2. **ORM coupling made it total.** `text_tsv` on the `Verse` model meant `select(Verse)` emitted
   the column on *every* verse read — new code required the migration before serving anything.
3. **Pipeline order.** `deploy` runs before `run-migrations`, so the dependent code was live first.
4. **False confidence from a false measurement.** Docstring said "low single-digit seconds —
   measured." Measured on a dev-stack table with no 1536-dim embedding column (~40× narrower rows)
   on unthrottled hardware. Off by three orders of magnitude.
5. **A CI timeout is not a bound on the database.** Killing the client orphaned the DDL, which
   held its lock 15 more minutes with no possible commit.

Contributing: the `production` approval gate applied *partially* (deploy approved, migration not),
and 16 runs sat queued behind it — a gate nobody services is latency, not control.

## What we learned

**About Postgres:**

- `ADD COLUMN ... GENERATED ... STORED` always rewrites; there is no concurrent form. Additive
  intent ≠ additive cost.
- A *queued* `ACCESS EXCLUSIVE` request blocks every later reader — a fast DDL can still take a
  site down by waiting. `lock_timeout` is the defense.
- Orphaned DDL survives its client. Only `statement_timeout` / `lock_timeout` (server-side) truly
  bound a migration; set them inside the revision or on the role, never trust the harness.
- Rolled-back rewrites leave no bloat (new relfilenode discarded) — but auto-grow they triggered
  is permanent, and it wedged Terraform (`storage_mb` must be in `ignore_changes` once
  `auto_grow_enabled = true`).
- GIN pending list: an index created empty then bulk-filled is invisible to the planner until
  `VACUUM` merges it (cost 1506 → 27 in our measurement). Removed entirely by not creating the
  index — see next point.

**About assumptions vs measurement — the biggest lesson:**

- The whole story's premise ("queries recompute `to_tsvector` per row") was **false for the main
  path**: `idx_verses_fts_simple` is an expression index that already stores the vectors.
  Benchmarked at production scale: routing `search_verses_text` through the side table was **37%
  slower** (0.105→0.144 ms); only the `ts_rank` sites won (2.750→0.238 ms, 11.5×).
- Consequences of measuring: `search_verses_text` untouched, the planned GIN index on `verse_tsv`
  dropped (no reader), BITB-095 Phase 2 (index drop) cancelled. Half the planned work was
  deleted by one hour of benchmarking.
- Even the fix's docs carried an unverified name (`search_verses_hybrid_multi` — doesn't exist).
  Errors propagate through copied prose; grep before writing.

**About process:**

- The winning design (side table + trigger) beat both textbook zero-downtime patterns
  (shadow-table copy, batched UPDATE) because both rewrite rows and therefore churn the 1536-dim
  HNSW index. The right answer was workload-specific, found by enumerating costs in a table, not
  by pattern-matching.
- Decoupling schema from ORM (`VerseTsv` separate, no relationship) is what made merge/deploy
  order irrelevant — the property whose absence turned a slow migration into a total outage.
- Splitting migration / backfill / query-switch into independently-safe, independently-verifiable
  steps meant each production action was boring: 4 verifiable gates instead of 1 big bang.
- During the incident, wrong-but-plausible hypotheses (lock queue; "prod recovers at phase 1
  commit") cost time. What cut through every time was **querying `pg_stat_activity` instead of
  reasoning about it**.

## What to avoid

- Any table-rewriting DDL on `verses`/`passages` inside the CI pipeline. If a rewrite is ever
  truly needed: scale compute first, run from tmux with server-side timeouts, off-peak.
- Mapping migration-dependent columns onto hot ORM models in the same release as the migration.
- Trusting `timeout-minutes`, dev-stack timings, or design docs' performance claims. Measure at
  403,856 rows or don't claim.
- Cancelling/killing a runner as a way to stop a migration — it stops nothing.
- Bumping `storage_mb` literals to chase auto-grow (breaks again at next doubling).
- `::` casts in raw SQL (`CAST(x AS t)` instead — the `:` trips the asyncpg bind guard that
  exists because of a prior production breakage).

## What we improve (owned follow-ups)

| story | what | status |
| --- | --- | --- |
| **BITB-097** | Pipeline: migrations-before-deploy (+ expand/contract rule in MIGRATION_GUIDELINES), functional-tests waits for migrations, job-level `lock_timeout`/`statement_timeout` < `timeout-minutes`, `deployment/**` in trigger paths, concurrency group (`cancel-in-progress: false`), approval-gate decision | 🎯 Todo — **highest value** |
| BITB-098 | Drop the two reader-less `_english` GIN indexes (evidence-first via `pg_stat_user_indexes`) | 🎯 Todo |
| BITB-099 | Decide on TLS: `sslmode=require` = `CERT_NONE` today | 🎯 Todo |
| done | `r0004` side-table form; timeouts inside the revision; resumable backfill; benchmark-backed query switch; Terraform `ignore_changes[storage_mb]` | ✅ #1001–#1003 |

**Process rules adopted going forward:**

1. Every migration states its **lock level and duration at production scale**, or says "unknown"
   honestly. "Measured" means measured on ≥400k rows with realistic row width.
2. Server-side timeouts in every revision (until BITB-097 sets them at job/role level).
3. Performance claims in stories require a benchmark before the *second* PR builds on them.
4. Migrations, bulk data movement, and query switches ship as separate, individually-reversible
   steps with explicit verification gates (`alembic current`, counts, parity).
5. New-code-old-schema compatibility is the default: schema artifacts live off the hot ORM models
   unless there's a reason.

## Cost accounting (honest)

Spent: 45 min downtime, +32 GB disk forever, ~36 h effort across 4 PRs and 4 stories.
Gained: ~2.5 ms per hybrid search query (low single-digit % of request time), a safe migration
pattern, and the five pipeline defects surfaced with evidence. **The performance prize never
justified the spend — the safety learnings are what we actually bought.** The honest counterfactual:
had the original `r0004` been benchmarked and lock-analyzed first, most of this file would not exist.
