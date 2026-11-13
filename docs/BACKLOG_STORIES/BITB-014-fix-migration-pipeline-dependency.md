# BITB-014: Fix Migration Pipeline Dependency Bug

**Priority:** P0 (Critical/Blocker)
**Status:** ✅ Done (PR #225 merged 2026-03-04)
**Size:** S (< 2 hours)
**Created:** 2026-03-04
**Completed:** 2026-03-04

---

## User Story

**As a** developer deploying database schema changes,
**I want** migrations to run automatically when migration scripts change,
**so that** schema updates are deployed reliably without manual intervention.

---

## Problem Statement

**Current Behavior:**

- PR #224 added migration `002_add_spiritual_contact_subject.py`
- The CI/CD pipeline did NOT execute the migration in production
- The database schema is out of sync with the codebase

**Root Cause:**
The `run-migrations` and `seed-database` jobs in `.github/workflows/azure-deploy.yml` use a flawed condition:

```yaml
needs.deploy.result != 'failure'
```

When a PR changes ONLY migration scripts (no backend/frontend code):

1. The `deploy` job is **skipped** (no code to deploy)
2. GitHub Actions sets `needs.deploy.result = 'skipped'`
3. The condition `'skipped' != 'failure'` evaluates to **FALSE** (unexpected behavior)
4. Migrations don't run, even though they changed

**Impact:**

- **Severity:** P0 - Critical (blocks all database migrations)
- **User Impact:** None directly (backend bug)
- **Developer Impact:** High - migrations silently fail to deploy

---

## Functional Requirements

- [ ] Migration jobs run when deploy succeeds (normal case)
- [ ] Migration jobs run when deploy is skipped (migration-only changes)
- [ ] Migration jobs do NOT run when deploy fails
- [ ] Seed database job uses same logic as migration job (consistency)
- [ ] Condition logic is documented with inline comments

---

## Non-Functional Requirements

- **Reliability:** Migration execution must be deterministic and predictable
- **Maintainability:** Condition logic must be clear and self-documenting
- **Safety:** Changes must not break existing deployment workflows
- **Testing:** Pre-commit checks validate YAML syntax before push

---

## Acceptance Criteria

**Code Changes:**

- [ ] `.github/workflows/azure-deploy.yml` line ~1025: `run-migrations` job condition fixed
- [ ] `.github/workflows/azure-deploy.yml` line ~1105: `seed-database` job condition fixed
- [ ] Condition changed from `needs.deploy.result != 'failure'` to:
      ```yaml
      (needs.deploy.result == 'success' || needs.deploy.result == 'skipped')
      ```
- [ ] Inline comments added explaining the logic

**Testing:**

- [ ] Pre-commit workflow validates YAML syntax (automatic via CI)
- [ ] PR passes all CI checks before merge
- [ ] Manual workflow dispatch test: migration from PR #224 runs successfully

**Documentation:**

- [ ] Tracking doc created: `docs/WIP/PR225-fix-migration-pipeline-dependency.md`
- [ ] Post-merge verification steps documented

**Post-Merge Actions:**

- [ ] Manually trigger workflow to run pending PR #224 migration:
      ```bash
      gh workflow run azure-deploy.yml --ref main \
        -f action=deploy \
        -f skip_build=true \
        -f skip_database_seed=true
      ```
- [ ] Verify in production database:
      ```sql
      SELECT conname, pg_get_constraintdef(oid)
      FROM pg_constraint
      WHERE conrelid = 'contact_submissions'::regclass
        AND contype = 'c'
        AND conname LIKE '%subject%';
      ```
      Expected: constraint includes `'spiritual'` in CHECK clause

---

## Tech Constraints

- Must not change deployment logic for backend/frontend code
- Must maintain backward compatibility with existing workflows
- Must work with GitHub Actions job dependency model
- YAML changes only - no backend/infrastructure changes

---

## Out of Scope

- Refactoring the entire deployment workflow
- Adding retry logic for failed migrations
- Creating a separate migration-only workflow
- Alembic integration (tracked in BITB-004)

---

## Implementation Notes

**Files Modified:**

- `.github/workflows/azure-deploy.yml` (2 job conditions)
- `docs/WIP/PR225-fix-migration-pipeline-dependency.md` (tracking doc)

**Branch:** `fix/migration-pipeline-dependency`
**PR:** #225 (to be created)

**Verification Steps:**

1. PR passes pre-commit checks
2. PR merges to main
3. Manually trigger workflow dispatch
4. Verify migration runs in Azure logs
5. Query production DB to confirm schema change

---

## Related Items

- **Blocked PR:** #224 (migration didn't execute)
- **Related Migration:** `scripts/migrations/002_add_spiritual_contact_subject.py`
- **Related Story:** BITB-004 (Alembic migration framework - long-term solution)
- **Workflow File:** `.github/workflows/azure-deploy.yml`

---

## Risk Assessment

**Risk Level:** Low
**Rationale:**

- Surgical change (2 lines modified)
- Only affects job execution conditions
- No code or infrastructure changes
- Easy to verify and rollback if needed

**Mitigation:**

- Pre-commit validates YAML syntax
- Manual testing before production rollout
- Database backup before migration execution
