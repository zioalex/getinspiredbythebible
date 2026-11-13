# BITB-126: Diagnose a Database Stamped Ahead of the Deploy Checkout

**Status:** 🚧 In Progress
**Priority:** P2 — no outage; a deploy failure that costs triage time every time it happens
**Size:** S (one preflight script + workflow wiring + tests)
**Created:** 2026-09-09
**Reported by:** deploy failure triage —
[run 33369807581](https://github.com/zioalex/getinspiredbythebible/actions/runs/33369807581)
**Affects:** `.github/workflows/azure-deploy.yml` (`run-migrations`), `scripts/`

## User Story

**As** whoever is holding a failed deploy,
**I want** the migration job to say *why* it cannot run,
**so that** I am not left reverse-engineering a bare `exit 255` to discover the
database was never broken in the first place.

## Context

Run 33369807581 failed on 2026-09-08 with no usable diagnosis:

```text
=== alembic current (before) ===
ERROR [alembic.util.messaging] Can't locate revision identified by 'r0006'
##[error]Process completed with exit code 255.
```

Nothing was wrong with production. The run was `run_attempt: 2` — a **re-run of
an older run**, replaying commit `12129b6a` (PR #1024, merged 2026-08-31), whose
tree holds only `r0001`..`r0005`. Revision `r0006` had landed in between via
`2d4ed40` (PR #1032) and deployed successfully on 2026-09-05, so the live
database was stamped at a revision the replayed checkout does not contain.
Alembic cannot resolve such a stamp, so `alembic current` died on the read —
before applying any DDL, and before the step's own preflight could speak.

Two things made this worse than it needed to be:

1. **The existing preflight could never fire for this case.** It tested
   `alembic current`'s *output* for an empty `alembic_version` row, so it sat
   downstream of the very command that had already exited 255. Ordering, not
   wording, was the defect.
2. **The failure is permanent and re-running is the intuitive response.** A
   stale run can never go green; without a message saying so, the natural
   reaction is to retry it.

Adjacent defect found while testing the fix against a real Postgres: the step
had no notion of how many revisions were actually pending, and the first
implementation of the replacement counted stamped ids rather than their
ancestry — reporting a database already at head as having 5 revisions to apply.
A stamp records the *latest* revision, not the full applied list.

## Changes

1. `scripts/alembic_preflight.py` (new) — reads `alembic_version` with a plain
   `SELECT` (no revision resolution, so an unknown id is data, not a crash) and
   compares it to the checkout's revision graph. Verdicts: `OK`, `UNSTAMPED`,
   `STALE_CHECKOUT`, `DIVERGED`, `MULTIPLE_HEADS`, each naming its own remedy.
   Connects via `scripts/migrations/utils.get_migration_connection_params()` —
   the same asyncpg path the legacy runner already uses in that job, rather
   than introducing a second driver into the deploy.
2. `.github/workflows/azure-deploy.yml` — the "Run Alembic migrations" step
   calls the preflight **before** any `alembic` command, replacing the inline
   `alembic current | tail` parsing (and the `set -o pipefail` that guarded the
   pipe it no longer has). The BITB-089 unstamped remedy moves into the script
   unchanged.
3. `api/tests/test_alembic_preflight.py` (new) — verdict, message and
   pending-count coverage, plus DB-free assertions against the repo's real
   revision graph (single head, no unreachable revisions).
4. `api/tests/test_deploy_workflow_migrations.py` — the preflight assertion
   follows the preflight: the step must *call* the script, and must call it
   before the first `alembic` command. Both guards were mutation-checked
   against a moved and a deleted preflight.

Explicitly **not** in scope: blocking stale re-runs at the workflow level
(a `DEPLOY_SHA`-is-an-ancestor-of-`main` gate), changing SSL/cert handling
(BITB-099 owns that), and retiring `scripts/migrations/`.

## Acceptance Criteria

- [x] A stamp absent from the checkout fails with a message naming the stamped
      revision, the checkout head, that the database is **not** broken, and that
      re-running cannot succeed
- [x] The unstamped remedy (`alembic stamp r0001`, BITB-089) is preserved
- [x] The preflight runs before any `alembic` command — asserted, not assumed
- [x] The success path reports the true number of pending revisions
- [x] Verified end-to-end against a real PostgreSQL 16: no `alembic_version`
      table, empty table, stamped at head, stamped behind head, stamped ahead
- [x] `pytest`, `black`, `ruff` and `mypy` clean on the changed files
- [ ] Green CI on the PR

## Related

- `.github/workflows/azure-deploy.yml` — `run-migrations` → "Run Alembic migrations"
- BITB-089 — Alembic adoption; the unstamped preflight this replaces
- BITB-097 — `run-migrations` ordering ahead of `deploy`
- BITB-112 — password percent-encoding in the same step
- `docs/MIGRATION_GUIDELINES.md` — expand/contract rules for revisions
