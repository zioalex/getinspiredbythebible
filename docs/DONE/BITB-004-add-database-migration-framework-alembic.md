---
id: BITB-004
status: done
priority: P1
size: L
rank: 810
---

# BITB-004: Add Database Migration Framework (Alembic)

**Status note:** (merged pending PR)

**Completed:** 2026-07-30

**As a** developer,
**I want** a version-controlled database migration system,
**so that** schema changes are tracked, reversible, and safely deployed.

**Acceptance Criteria:**

- [x] Alembic installed and configured (`api/alembic/`, run from `api/`)
- [x] Initial migration created from current schema (`api/alembic/versions/r0001_baseline_schema.py`,
      generated via `--autogenerate` against a live local Postgres+pgvector, then hand-verified)
- [x] Migration runs successfully on fresh database (`alembic upgrade head` creates all 9
      ORM-backed tables + `alembic_version`)
- [x] Rollback tested and working (`alembic downgrade base` removes all 9 tables cleanly,
      re-`upgrade head` recreates them; proven both manually and in
      `api/tests/test_alembic_migrations.py`)
- [x] CI runs migration check before deploying (new `alembic-migrations` job in
      `.github/workflows/test_update.yml`: upgrade → check → downgrade base → upgrade → history,
      read-only `alembic check`, never `--autogenerate`, on its own ephemeral Postgres service)
- [x] Documentation updated with migration workflow (`api/alembic/README.md`,
      `docs/MIGRATION_GUIDELINES.md` "Long-Term Solution: Alembic" section)

**Tech Constraints:**

- Must work with existing SQLAlchemy models — yes, `target_metadata` is
  `[ScriptureBase.metadata, FeedbackBase.metadata]` from `scripture/models.py` / `feedback/models.py`
- Must work with asyncpg connection pool — `env.py` reuses
  `scripture.database.get_async_database_url()` for the same SSL convention as the app
- Must support zero-downtime deployments (future-proofing) — `run_migrations_offline()`
  (`alembic upgrade head --sql`) is kept working for a future DBA-reviewed, zero-downtime path

**Out of Scope (respected):**

- Converting existing production database (manual one-time task) — **not done in this PR**;
  see the "operator runbook note" in `docs/MIGRATION_GUIDELINES.md` (`alembic stamp r0001`,
  executes zero DDL, is a deliberate future manual step)
- Auto-generated migrations from model changes in CI — CI only ever runs `alembic check`
  (read-only), never `--autogenerate`
- Backfilling the 5 legacy non-ORM tables (`sessions`, `verse_topics`, `rate_limit_hits`,
  `rate_limit_sessions`, `schema_migrations`) into Alembic — still owned by
  `scripts/migrations/`/`scripts/init.sql`, invisible to Alembic by design (`include_name`
  allowlist in `env.py`)

**Related:** TASKS.md #1.5
