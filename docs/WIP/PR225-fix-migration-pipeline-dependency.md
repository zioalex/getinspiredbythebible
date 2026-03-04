# PR #225: Fix Migration Pipeline Dependency Bug

**Status:** In Progress
**Started:** 2026-03-04
**Priority:** P0 (Critical - Blocks database migrations)

## Summary

Fix critical bug in CI/CD pipeline where database migrations don't run when only migration scripts
change (without backend/frontend changes). This caused PR #224's migration
(`002_add_spiritual_contact_subject.py`) to not execute in production.

## Root Cause

The `run-migrations` job in `.github/workflows/azure-deploy.yml` has a dependency flaw:

```yaml
run-migrations:
  needs: [changes, deploy]
  if: >-
    always() && github.event_name != 'pull_request' && needs.deploy.result != 'failure' &&
    (needs.changes.outputs.migration_scripts == 'true' ||
     github.event_name == 'workflow_dispatch')
```

**Problem:** The condition `needs.deploy.result != 'failure'` evaluates to `false` when deploy is
**skipped** (not run), because a skipped job has result `'skipped'`, not a non-failure state.

**Impact:** If a PR only changes migration scripts:

1. `deploy` job is skipped (no backend/frontend changes)
2. `run-migrations` evaluates: `'skipped' != 'failure'` → `false`
3. Migration job doesn't run, even though migrations changed

## Fix

Change the condition to explicitly allow both `success` and `skipped` deploy states:

**Before:**

```yaml
needs.deploy.result != 'failure'
```

**After:**

```yaml
(needs.deploy.result == 'success' || needs.deploy.result == 'skipped')
```

This explicitly allows:

- **success** - migrations run after a successful deploy
- **skipped** - migrations run even when deploy is skipped (migration-only changes)

Applied to both:

- `run-migrations` job (line 1025-1029)
- `seed-database` job (line 1104-1108) - same issue

## Changes Made

- [x] Updated `run-migrations` job condition
- [x] Updated `seed-database` job condition
- [x] Added inline comments explaining the logic
- [ ] Opened PR
- [ ] CI passes
- [ ] Merged to main
- [ ] Manual workflow_dispatch to run PR #224 migration

## Testing Plan

1. **Pre-merge:** CI pre-commit workflow validates YAML syntax
2. **Post-merge:** Manually trigger workflow_dispatch to run pending migration from PR #224
3. **Validation:** Verify migration `002_add_spiritual_contact_subject.py` runs successfully
4. **Future validation:** Next PR that only changes migrations should trigger the job

## Impact

- **Severity:** P0 - Critical
- **User Impact:** None directly (backend bug, not user-facing)
- **Developer Impact:** High - ensures migrations always run when changed
- **Risk:** Low - fix is surgical, only changes job conditions

## Verification

After merge and manual trigger:

```sql
-- Verify constraint was updated
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'contact_submissions'::regclass
  AND contype = 'c'
  AND conname LIKE '%subject%';
```

Expected result: constraint includes `'spiritual'` in the CHECK clause.

## Related

- **Blocked PR:** #224 (migration didn't run)
- **Related Migration:** `scripts/migrations/002_add_spiritual_contact_subject.py`
- **Workflow File:** `.github/workflows/azure-deploy.yml`
