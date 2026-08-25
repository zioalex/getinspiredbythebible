<!--
Title must follow Conventional Commits (enforced by commitlint):
  type(scope): short imperative summary
  e.g. feat(api): add per-language model fallback chain (BITB-068)
Keep the PR small and focused on a single concern.
-->

## What

<!-- Bullet-point summary of the changes and why they're needed.
     Link the backlog story (BITB-xxx / docs/BACKLOG_STORIES/) if one exists. -->

-

## Test plan

<!-- How a reviewer can verify this works — exact commands, and what you ran. -->

- [ ] Tests added/updated for changed behaviour (`make test`, `cd frontend && npm test`, `./gradlew test` as applicable)
- [ ] `make pre-commit` passes locally
- [ ]

## Migration checklist

<!-- Only fill this in if this PR adds or changes an Alembic revision
     (api/alembic/versions/**) -- delete the whole section otherwise.
     See docs/MIGRATION_GUIDELINES.md, "Locking & scale (Alembic revisions)". -->

- [ ] Docstring states lock level + duration at production scale (>=400k rows), or says "unknown"
- [ ] No table-rewriting DDL in the CI path (`ADD COLUMN ... STORED`, `ALTER COLUMN ... TYPE`, plain `DROP INDEX`/`CREATE INDEX` on a hot table, etc.)
- [ ] `SET LOCAL lock_timeout` / `statement_timeout` set inside the revision
- [ ] Backward-compatible with the currently-deployed app (Rule #7, expand/contract)
- [ ] `alembic downgrade -1` then `alembic upgrade head` run locally

## Notes

<!-- Optional: scope cuts, follow-ups deferred to another PR, migration or
     rollout steps, new dependencies/permissions and why. Delete if empty. -->
