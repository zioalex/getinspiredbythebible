# Current Status: What's Done & What's Missing (2026-03-04)

**Last Updated:** 2026-03-04 (after migration failure discovery)
**Status:** 🔴 BLOCKED — Migration scripts have SSL connection bug

---

## 🎯 Quick Summary

### ✅ What's Done

- PR #225: Fixed migration pipeline workflow ✅ MERGED
- PR #226: Consolidated agent configuration ✅ MERGED
- Migration guidelines document created ✅

### 🔴 What's Blocking

- **CRITICAL:** Migration scripts can't connect to Azure DB with SSL
- Error: `asyncpg.exceptions.CantChangeRuntimeParamError: parameter "ssl" cannot be changed now`
- **Impact:** PR #224 migration (`002_add_spiritual_contact_subject.py`) still not run in production

### 🎯 Next Action Required

Fix BITB-016: Update migration scripts to handle SSL correctly (< 1 hour fix)

---

## 📋 Detailed Status

### ✅ BITB-014: Fix Migration Pipeline Dependency Bug (DONE)

**Status:** ✅ Merged (PR #225)
**Problem Solved:** Migrations now run when only migration files change
**Outcome:** Pipeline workflow fixed permanently

**What Changed:**

- `.github/workflows/azure-deploy.yml` conditions fixed
- Changed from `needs.deploy.result != 'failure'`
- To: `(needs.deploy.result == 'success' || needs.deploy.result == 'skipped')`

---

### ✅ BITB-015: Consolidate Agent Configuration (DONE)

**Status:** ✅ Merged (PR #226)
**Problem Solved:** Agent configuration consolidated, clear boundaries established
**Outcome:** Single source of truth in `opencode.json`

**What Changed:**

- Enhanced product-owner agent prompt with "DO NOT CODE" guardrails
- Deleted `CLAUDE.md` (moved to opencode.json)
- Cleaned up global config

---

### 🔴 BITB-016: Fix Migration Scripts SSL Connection Error (BLOCKING)

**Status:** 🔴 Todo — CRITICAL BLOCKER
**Priority:** P0
**Problem:** Migration scripts fail to connect to Azure PostgreSQL

**Error Message:**

```
asyncpg.exceptions.CantChangeRuntimeParamError: parameter "ssl" cannot be changed now
```

**Root Cause:**
Migration scripts in `scripts/migrations/` pass the full DATABASE_URL (including `?ssl=require`) directly to `asyncpg.connect()`. Unlike psycopg2, asyncpg doesn't accept SSL configuration as a URL query parameter — it must be passed as a separate `ssl` argument.

**Current Broken Code:**

```python
# ❌ This fails in Azure with SSL
database_url = "postgresql://user:pass@host/db?ssl=require" # pragma: allowlist secret
conn = await asyncpg.connect(database_url)
```

**Required Fix:**

```python
# ✅ This works in all environments
from utils import get_migration_connection_params

clean_url, conn_kwargs = get_migration_connection_params(settings.database_url)
conn = await asyncpg.connect(clean_url, **conn_kwargs)
```

**Files Needing Fix:**

1. `scripts/migrations/utils.py` (NEW — create helper function)
2. `scripts/migrations/001_add_feedback_tables.py` (update connection)
3. `scripts/migrations/002_add_spiritual_contact_subject.py` (update connection)

**Solution Reference:**
The backend already handles this correctly in `api/scripture/database.py` → `get_async_database_url()`. Migration scripts need the same pattern.

**Impact:**

- **Blocks:** PR #224 migration execution
- **Severity:** P0 — No migrations can run until fixed
- **Time to Fix:** < 1 hour

---

## 📚 Documentation Created

### New Documents

1. **`docs/BACKLOG_STORIES/BITB-014-fix-migration-pipeline-dependency.md`**
   - Full user story for pipeline fix
   - Completed ✅

2. **`docs/BACKLOG_STORIES/BITB-015-consolidate-agent-configuration.md`**
   - Full user story for agent config consolidation
   - Completed ✅

3. **`docs/BACKLOG_STORIES/BITB-016-fix-migration-ssl-connection.md`**
   - Full user story for SSL connection fix
   - Awaiting implementation 🔴

4. **`docs/MIGRATION_GUIDELINES.md`** ⭐ NEW
   - Comprehensive guide for future migrations
   - Includes migration template
   - Best practices and common patterns
   - Troubleshooting guide
   - Prevents recurrence of SSL issue

### Updated Documents

5. **`docs/BACKLOG.md`**
   - BITB-014 marked as Done ✅
   - BITB-015 marked as Done ✅
   - BITB-016 added as P0 blocker 🔴
   - Last updated: 2026-03-04

6. **`docs/WIP/SUMMARY-2026-03-04-what-we-did.md`**
   - Summary of completed work
   - Status of PRs

---

## 🚦 What Needs to Happen Next

### Immediate Action (< 1 hour)

**Fix BITB-016** to unblock migrations:

1. **Create helper function:**
   - File: `scripts/migrations/utils.py`
   - Function: `get_migration_connection_params(database_url: str) -> tuple[str, dict]`
   - Logic: Parse URL, extract SSL params, create SSL context, return clean URL + kwargs

2. **Update migration scripts:**
   - `001_add_feedback_tables.py` — replace connection logic
   - `002_add_spiritual_contact_subject.py` — replace connection logic

3. **Test locally:**

   ```bash
   export DATABASE_URL="postgresql://user:pass@localhost:5432/bible_db" # pragma: allowlist secret
   python scripts/migrations/001_add_feedback_tables.py
   ```

4. **Create PR:**

   ```bash
   git checkout -b fix/migration-ssl-connection
   git add scripts/migrations/
   git commit -m "fix(db): handle SSL parameters correctly in migration scripts"
   git push origin fix/migration-ssl-connection
   gh pr create --title "Fix migration SSL connection error"
   ```

5. **After PR merges, run migrations:**

   ```bash
   gh workflow run azure-deploy.yml --ref main \
     -f action=deploy \
     -f skip_build=true \
     -f skip_database_seed=true
   ```

6. **Verify in production:**

   ```bash
   psql $DATABASE_URL -c "
   SELECT conname, pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conrelid = 'contact_submissions'::regclass
     AND contype = 'c'
     AND conname LIKE '%subject%';"
   ```

   Expected: Constraint should include `'spiritual'`

---

## 📊 Progress Summary

| Story | Priority | Status | PR | Notes |
|-------|----------|--------|-----|-------|
| BITB-014 | P0 | ✅ Done | #225 merged | Pipeline fix complete |
| BITB-015 | P1 | ✅ Done | #226 merged | Agent config consolidated |
| BITB-016 | P0 | 🔴 Todo | TBD | BLOCKING — SSL connection bug |

---

## 🎯 Success Metrics

### Completed

- ✅ 2 PRs merged today
- ✅ 2 user stories closed (BITB-014, BITB-015)
- ✅ Pipeline workflow fixed permanently
- ✅ Agent configuration consolidated
- ✅ Migration guidelines documented

### Pending

- ⏳ 1 PR needed (BITB-016 fix)
- ⏳ Migration from PR #224 not yet run
- ⏳ Production DB constraint not yet updated

---

## 🔍 Root Cause Analysis

**Why did the migration fail?**

1. **Initial Problem:** Pipeline didn't run migrations when only migration files changed (BITB-014)
   - **Status:** FIXED ✅ (PR #225)

2. **Discovered Problem:** Migration scripts have SSL connection bug (BITB-016)
   - **Status:** NOT FIXED 🔴 (this is what we discovered today)

**Why wasn't this caught earlier?**

- Migrations were never tested in Azure production environment (due to pipeline bug)
- Local dev doesn't use SSL, so issue didn't surface in testing
- Backend code handles SSL correctly, but migration scripts were written without referencing it

**Prevention:**

- `docs/MIGRATION_GUIDELINES.md` now documents the correct pattern
- Migration template includes SSL-safe connection code
- All future migrations will follow the template

---

## 📞 Who Needs to Know

**Human/Team:**

- Migration scripts are broken in production
- Need to fix BITB-016 before any migrations can run
- PR #224 migration is still pending (waiting for BITB-016 fix)

**Next Sprint:**

- Consider BITB-004 (Alembic migration framework) to avoid manual migration issues

---

## 🎯 Definition of "Done" for Current Work

### When can we mark today's work complete?

- [x] PR #225 merged (pipeline fix)
- [x] PR #226 merged (agent config)
- [ ] PR for BITB-016 created and merged
- [ ] Migrations run successfully in Azure
- [ ] Production DB verified: `contact_submissions` constraint includes `'spiritual'`
- [ ] Tracking doc moved to `docs/DONE/`

---

## 🚀 Next Steps for Human

### Option A: I can fix BITB-016 myself

```bash
# Create the fix following docs/BACKLOG_STORIES/BITB-016-fix-migration-ssl-connection.md
# Use the migration template from docs/MIGRATION_GUIDELINES.md
```

### Option B: Delegate to orchestrator

The product-owner agent (me) can delegate BITB-016 to the orchestrator with the full user story embedded. Just say "fix BITB-016" and I'll handle the delegation.

### Option C: Wait and do it later

BITB-016 is a P0 blocker but non-urgent if no other migrations are pending. The fix is small (< 1 hour).

---

**Recommendation:** Option B — Let me delegate to orchestrator. The user story is complete and ready to implement.

---

## 📎 References

- **User Stories:** `docs/BACKLOG_STORIES/BITB-014-*.md`, `BITB-015-*.md`, `BITB-016-*.md`
- **Guidelines:** `docs/MIGRATION_GUIDELINES.md` (use this for all future migrations!)
- **Backend SSL Reference:** `api/scripture/database.py` → `get_async_database_url()`
- **Workflow:** `.github/workflows/azure-deploy.yml` → `run-migrations` job
- **Failed Run:** Check GitHub Actions logs for latest azure-deploy.yml run

---

**Status:** 🔴 Waiting for BITB-016 fix to unblock migrations
