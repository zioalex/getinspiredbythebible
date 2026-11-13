# BITB-090: Remove `init_db()` / `create_all()` Once Alembic Owns the Schema

**Status:** ✅ Done (2026-09-04)
**Priority:** P2
**Size:** S
**Created:** 2026-07-31
**Depends on:** BITB-089 — **hard** dependency. Doing this first removes the only thing creating
the schema, and nothing has replaced it yet.

## User Story

**As a** maintainer, **I want** exactly one system allowed to create schema, **so that** the
migration history is a truthful record of the database rather than one of two competing accounts
of it.

## Why Now

`api/main.py:201` calls `init_db()` on startup, which runs
`ScriptureBase.metadata.create_all` and `FeedbackBase.metadata.create_all`
(`api/scripture/database.py:175-186`). That is a second schema authority sitting beside Alembic.

While both exist, a table added to an ORM model appears in the database **on the next app boot**,
with no revision, no `alembic_version` change, and no record that it happened. Alembic then
believes the database is at `r0001` when it is not. The next `alembic check` reports drift that
looks like a bug in the migration rather than what it is — a schema change that bypassed the
system entirely.

This is latent today (Alembic is inert, `create_all` is the only creator, and they happen to
agree). It becomes a real divergence the moment BITB-089 makes Alembic authoritative. Hence: after
089, not before, and not much later.

## Design Notes

`init_db()` does more than `create_all` — read it before deleting anything. Whatever else it sets
up (extensions, connection warm-up, startup checks) must survive; only the `create_all` calls are
in question.

Local and test environments currently rely on `create_all` to get a usable database from nothing.
Removing it means fresh environments must run `alembic upgrade head` instead, so this story owns
that transition too: `docker-compose` flows, `docs/LOCAL_DEVELOPMENT.md`, and any test fixture that
assumes tables appear by themselves.

Note `api/main.py` catches `init_db()` failures and boots anyway — flagged as a root cause in
`docs/audits/2026-07-adversarial-audit.md:174`. Worth resolving the swallowed-failure behaviour in
the same pass rather than carrying it forward.

## Acceptance Criteria

- [x] BITB-089 shipped and Alembic has applied at least one real revision to production
- [x] `create_all()` calls removed from `api/scripture/database.py`
- [x] Everything else `init_db()` does is preserved (or its removal justified explicitly) — the
      only other behavior was the pgvector `CREATE EXTENSION` (now owned by `r0001`) and a
      pool-warming connection (preserved as the connectivity check `check_db_connection()`)
- [x] A fresh local database is fully usable via `alembic upgrade head` — verified from empty
- [x] Test fixtures no longer depend on `create_all`; the suite passes from an empty database
- [x] `docs/LOCAL_DEVELOPMENT.md` updated with the new "first run" step
- [x] CI proves it: a job that starts empty, runs only `alembic upgrade head`, and boots the app
- [x] Startup no longer silently swallows a schema-setup failure — `main.py` now re-raises so a
      dead database crash-loops the revision instead of serving traffic (audit finding E7 resolved)

## Resolution

`init_db()` was replaced with `check_db_connection()`, a plain `SELECT 1` ping. The pgvector
extension it used to create is already owned by revision `r0001`; nothing else in the function
needed preserving beyond opening the first pool connection. `api/main.py`'s lifespan now re-raises
on failure instead of logging and continuing. CI's `alembic-migrations` job gained a final step
that boots the FastAPI app (`TestClient` + `GET /health/live`) against a database that has had
nothing but `alembic upgrade head` run against it, and `backend-tests` now runs
`alembic upgrade head` before pytest so the integration suite runs against the real migrated
schema instead of a hand-rolled copy.

## Out of Scope

- Changing the schema itself
- The 5 legacy non-ORM tables — BITB-091; they are created by `scripts/init.sql` /
  `scripts/migrations/`, not by `create_all`, so they are unaffected here

## Related

- BITB-089 — prerequisite
- BITB-004 / PR #948 — noted this removal as a deferred follow-up
- `api/main.py:201`, `api/scripture/database.py:175-186`
- `docs/audits/2026-07-adversarial-audit.md:174` — swallowed `init_db()` failure
