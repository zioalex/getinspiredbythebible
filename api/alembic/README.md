# Alembic migrations

Run every command from `api/` (this repo's convention). `DATABASE_URL` must be
set (see `api/config.py::Settings.database_url`) — Alembic derives its
connection from `scripture.database.get_async_database_url()` at runtime, so
there is nothing to configure in `alembic.ini` itself.

## Common commands

```bash
cd api

# Generate a new migration from model changes (autogenerate diffs the ORM
# metadata against the live database named by DATABASE_URL)
alembic revision --autogenerate -m "short description"

# Apply all pending migrations
alembic upgrade head

# Roll back the most recent migration / all the way to an empty schema
alembic downgrade -1
alembic downgrade base

# Verify the database matches the ORM models with zero DDL side effects
# (read-only — this is what CI runs, never --autogenerate)
alembic check

# List applied/pending revisions
alembic history --verbose
```

Never point any of the above at the production database from a local
machine or a PR. `DATABASE_URL` should always resolve to `localhost` /
`127.0.0.1` / a CI service container in this workflow.

For the two destructive entry points that run `downgrade base` unattended —
`make alembic-roundtrip` and `api/tests/test_alembic_migrations.py` — that
rule is enforced, not just documented. Both parse the host out of
`DATABASE_URL` and refuse to proceed unless it is one of `localhost`,
`127.0.0.1`, `postgres`, `db` (the make target exits non-zero; the tests
skip). To approve a different local/CI host — say a docker-compose service
under another name — set `ALEMBIC_TEST_ALLOW_HOST=1`. The check is against
that exact value, so `ALEMBIC_TEST_ALLOW_HOST=0` leaves the guard armed
rather than silently disabling it.

## Before you write a revision

Two rules in `../../docs/MIGRATION_GUIDELINES.md` are binding, not
suggestions — both exist because of a specific production outage:

- **Rule #7 (expand/contract).** `run-migrations` runs before `deploy`, so
  every migration must be compatible with the app version currently serving
  traffic. See `../../docs/MIGRATION_GUIDELINES.md` under "Critical Rules",
  Rule #7.
- **["Locking & scale (Alembic
  revisions)"](../../docs/MIGRATION_GUIDELINES.md#locking--scale-alembic-revisions).**
  State the lock level and duration at production scale, keep
  table-rewriting DDL out of the CI path, set `SET LOCAL lock_timeout` /
  `statement_timeout` in every revision, and use `CAST(x AS t)` rather than
  `::` in raw SQL.

`api/tests/test_alembic_migrations.py` enforces the `lock_timeout` rule
mechanically for every new revision. The rest is enforced in review, backed
by the migration checklist in the PR template.

## Three invariants

1. **The `include_name` allowlist is intentional, not a bug.** Five tables —
   `sessions`, `verse_topics`, `rate_limit_hits`, `rate_limit_sessions`,
   `schema_migrations` — exist in every real database (created by
   `scripts/init.sql` / `scripts/migrations/`) but have no SQLAlchemy ORM
   model. `env.py`'s `include_name()` allowlists only tables backed by
   `ScriptureBase.metadata` / `FeedbackBase.metadata`, so those five stay
   invisible to Alembic. Without this filter, the very first
   `--autogenerate` would propose `op.drop_table(...)` for all five.
   `include_object()` does the equivalent job for the raw-SQL-created
   indexes (FTS GIN indexes, per-translation partial HNSW indexes) that
   likewise have no ORM-side definition. These tables/indexes are not meant
   to be adopted here — see `docs/MIGRATION_GUIDELINES.md`.

2. **`compare_type=False` is intentional — and it means no column type is
   ever compared, not just Vector columns.** `Verse.embedding` /
   `Passage.embedding` / `Topic.embedding` are `Vector(settings.embedding_dimensions)`,
   and that dimension is environment-dependent (1024 for the ollama-backed
   local/CI default, 1536 for `azure_openai` in prod — see `api/config.py`).
   With column-type comparison on, `alembic check`/autogenerate would report
   "drift" purely because two environments run different embedding
   providers, not because anyone changed the schema. But `compare_type` is a
   single on/off switch for the whole comparison, not something that can be
   scoped to just those three columns — turning it off to avoid the Vector
   false-positive means **`alembic check` verifies structure only**
   (tables/columns/indexes/constraints present or not) and **never verifies
   that any column's declared type still matches what's in the database**. A
   `varchar(50)` silently becoming a `varchar(100)`, or a `timestamp`
   drifting from a `timestamptz`, would pass `alembic check` cleanly. See
   BITB-094 (`docs/BACKLOG_STORIES/BITB-094-audit-column-types-against-production.md`,
   `docs/audits/BITB-094-column-type-audit.md`), which audited this blind
   spot directly rather than through `alembic check`. Anyone who wants
   type-level assurance should run `scripts/audit_column_types.py` — a
   standalone tool that reuses this file's `target_metadata`/`include_name`/
   `include_object` but forces `compare_type=True` for the comparison; see
   that script's docstring for how to point it at a schema-only production
   restore. It is deliberately not part of `alembic check` or any CI gate
   (see the audit doc's "Decision: not a CI gate" section).

3. **`alembic_version` and `schema_migrations` are two different, coexisting
   systems, not a conflict.** `schema_migrations` (see
   `scripts/migrations/run_migrations.py`) is the hand-rolled tracker for
   everything under `scripts/migrations/`, which is frozen as historical
   record. `alembic_version` is Alembic's own bookkeeping table for
   everything under `api/alembic/versions/`, kept at its default name so the
   two never collide. New schema changes go through Alembic; nothing writes
   to `schema_migrations` anymore.

## `CREATE INDEX CONCURRENTLY`

`CONCURRENTLY` cannot run inside a transaction block, but Alembic wraps each
migration in one by default. A future migration that needs it must open an
autocommit block explicitly:

```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("CREATE INDEX CONCURRENTLY ... ")
```

See `scripts/migrations/007_partial_hnsw_verse_indexes.py` for the same
constraint solved in the legacy system (there, by issuing each statement
outside any `asyncpg` transaction).
