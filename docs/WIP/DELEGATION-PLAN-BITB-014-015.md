# 🚀 Delegation Plan: BITB-014 & BITB-015

**Created:** 2026-03-04
**Status:** ⏳ Awaiting Human Approval
**Product Owner:** Claude (Product Owner Agent)

---

## Overview

Two infrastructure improvements are ready for implementation:

1. **BITB-014:** Fix critical migration pipeline bug (P0)
2. **BITB-015:** Consolidate agent configuration (P1)

Both stories are documented, ready to delegate to orchestrator for implementation.

---

## 📋 Story 1: BITB-014 - Fix Migration Pipeline Dependency Bug

### Summary

Fix CI/CD bug where database migrations don't run when only migration scripts change.

### Priority & Impact

- **Priority:** P0 (Critical/Blocker)
- **Size:** S (< 2 hours)
- **Risk:** Low (surgical YAML change)
- **User Impact:** None directly (backend bug)
- **Developer Impact:** Critical - unblocks all database migrations

### What's Already Done

✅ Root cause analysis complete
✅ Solution designed and documented
✅ Tracking doc created
✅ Script prepared (`create-pr-225.sh`)

### What Needs to Be Done

- [ ] Create branch `fix/migration-pipeline-dependency`
- [ ] Modify `.github/workflows/azure-deploy.yml` (2 job conditions)
- [ ] Run `make pre-commit`
- [ ] Commit changes
- [ ] Open PR #225
- [ ] Wait for CI to pass
- [ ] Report back with PR URL

### Full User Story

See: `docs/BACKLOG_STORIES/BITB-014-fix-migration-pipeline-dependency.md`

---

## 📋 Story 2: BITB-015 - Consolidate Agent Configuration

### Summary

Remove duplicate agent configuration, enhance product-owner guardrails, follow OpenCode best practices.

### Priority & Impact

- **Priority:** P1 (High)
- **Size:** S (< 3 hours)
- **Risk:** Low (config-only changes, reversible)
- **User Impact:** None (internal configuration)
- **Developer Impact:** Medium - improves agent behavior and maintainability

### What's Already Done

✅ Configuration architecture researched
✅ Best practices documented
✅ Duplication identified

### What Needs to Be Done

- [ ] Create branch `refactor/consolidate-agent-config`
- [ ] Edit `./opencode.json` (enhance product-owner agent prompt)
- [ ] Delete `CLAUDE.md`
- [ ] Clean up `~/.config/opencode/opencode.json` (local, not committed)
- [ ] Run `make pre-commit`
- [ ] Commit changes (excludes global config cleanup)
- [ ] Open PR #226
- [ ] Wait for CI to pass
- [ ] Report back with PR URL

### Full User Story

See: `docs/BACKLOG_STORIES/BITB-015-consolidate-agent-configuration.md`

---

## 🎯 Delegation Approach

### Option A: Delegate Both Stories Together (Recommended)

**Pros:**

- Both are infrastructure improvements
- Both are small, low-risk changes
- Can be worked in parallel
- Faster overall completion

**Cons:**

- Two PRs to track simultaneously

### Option B: Delegate Sequentially (BITB-014 → BITB-015)

**Pros:**

- Focus on P0 blocker first
- Easier to track progress
- Lower cognitive load

**Cons:**

- Takes longer overall
- BITB-015 waits for BITB-014 to complete

**My Recommendation:** **Option A** - delegate both together. They're independent, low-risk, and can be done in parallel.

---

## 📝 Delegation Prompts (Ready to Use)

### Delegation for BITB-014

```
TASK: Implement BITB-014 - Fix Migration Pipeline Dependency Bug

USER STORY:
As a developer deploying database schema changes,
I want migrations to run automatically when migration scripts change,
so that schema updates are deployed reliably without manual intervention.

PROBLEM:
- PR #224's migration `002_add_spiritual_contact_subject.py` never ran in production
- Root cause: Pipeline condition `needs.deploy.result != 'failure'` evaluates to FALSE when deploy is skipped
- When only migrations change (no code changes), deploy job is skipped → migrations don't run

FUNCTIONAL REQUIREMENTS:
- Migration jobs run when deploy succeeds (normal case)
- Migration jobs run when deploy is skipped (migration-only changes)
- Migration jobs do NOT run when deploy fails
- Seed database job uses same logic (consistency)
- Condition logic is documented with inline comments

ACCEPTANCE CRITERIA:
- `.github/workflows/azure-deploy.yml` line ~1025: `run-migrations` condition fixed
- `.github/workflows/azure-deploy.yml` line ~1105: `seed-database` condition fixed
- Condition changed from `needs.deploy.result != 'failure'` to:
  (needs.deploy.result == 'success' || needs.deploy.result == 'skipped')
- Inline comments added explaining the logic
- Pre-commit workflow validates YAML syntax
- PR passes all CI checks

TECH CONSTRAINTS:
- YAML changes only - no backend/infrastructure changes
- Must maintain backward compatibility with existing workflows
- Must work with GitHub Actions job dependency model
- Must run `make pre-commit` before committing

OUT OF SCOPE:
- Refactoring entire deployment workflow
- Adding retry logic for failed migrations
- Alembic integration (separate story)

IMPLEMENTATION NOTES:
- Branch name: `fix/migration-pipeline-dependency`
- PR number: #225
- Files to modify: `.github/workflows/azure-deploy.yml`
- Tracking doc already exists: `docs/WIP/PR225-fix-migration-pipeline-dependency.md`
- Script exists but DON'T use it: `create-pr-225.sh` (manual implementation preferred)

TESTING:
- Pre-commit checks must pass
- CI must validate YAML syntax
- No functional testing needed (logic-only change)

DELIVERABLES:
1. Branch created
2. Changes committed
3. PR opened with descriptive title and body
4. CI passing
5. Report back with PR URL

POST-MERGE ACTIONS (for human to execute):
gh workflow run azure-deploy.yml --ref main -f action=deploy -f skip_build=true -f skip_database_seed=true

Then verify in production DB:
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'contact_submissions'::regclass
  AND contype = 'c'
  AND conname LIKE '%subject%';

Expected: constraint includes 'spiritual' in CHECK clause.
```

### Delegation for BITB-015

```
TASK: Implement BITB-015 - Consolidate Agent Configuration

USER STORY:
As a product owner and team member,
I want agent configurations to follow best practices with clear separation of concerns,
so that agents have consistent instructions and don't duplicate configuration.

PROBLEM:
- `CLAUDE.md` duplicates instructions that should be in `opencode.json`
- Both `~/.config/opencode/opencode.json` and `./opencode.json` contain identical agent definitions
- Product-owner agent lacks explicit "DO NOT CODE" guardrails
- Delegation protocol doesn't emphasize embedding full user stories

FUNCTIONAL REQUIREMENTS:
- Product-owner agent prompt moved entirely to `./opencode.json`
- Product-owner prompt includes "=== CRITICAL RULE: YOU ARE NOT AN ENGINEER ===" section
- Product-owner prompt includes "=== DELEGATION PROTOCOL (MANDATORY) ===" with examples
- Product-owner prompt includes "=== PROGRESS MONITORING (MANDATORY) ===" (30-min check-ins)
- Product-owner prompt includes "=== PROJECT-SPECIFIC KNOWLEDGE ===" section
- Emphasis on embedding full user stories when delegating (don't reference external files)
- `CLAUDE.md` deleted
- `~/.config/opencode/opencode.json` cleaned up (local change, not in PR)

ACCEPTANCE CRITERIA:
- `./opencode.json` updated with enhanced product-owner agent prompt (all sections listed above)
- `CLAUDE.md` deleted
- `~/.config/opencode/opencode.json` (global config) cleaned up locally:
  - Remove all agent definitions (93 lines → ~20 lines)
  - Keep ONLY provider/model configuration (Ollama, qwen models)
  - NOTE: This file is NOT committed to Git (local change only)
- Pre-commit checks pass (validate JSON syntax)
- Agent loads correctly and follows delegation protocol
- PR includes only: opencode.json changes + CLAUDE.md deletion (NOT global config)

TECH CONSTRAINTS:
- Project config (`./opencode.json`) has highest precedence in OpenCode
- Project config committed to Git; global config NOT committed
- Must maintain valid JSON syntax
- Must not break existing agent functionality
- Changes must be reversible

OUT OF SCOPE:
- Creating new agent types
- Reorganizing other agents (orchestrator, engineer, etc.)
- Changing provider/model configuration

IMPLEMENTATION NOTES:
- Branch name: `refactor/consolidate-agent-config`
- PR number: #226
- Files to modify:
  1. `./opencode.json` (enhance product-owner agent)
  2. `CLAUDE.md` (delete)
  3. `~/.config/opencode/opencode.json` (clean up locally, NOT in PR)

ENHANCED AGENT PROMPT STRUCTURE:
Add these sections to product-owner agent in opencode.json:

1. === CRITICAL RULE: YOU ARE NOT AN ENGINEER ===
   - You define WHAT to build, not HOW
   - NEVER make code changes directly
   - NEVER run git commands (branch, commit, push)
   - NEVER merge PRs
   - ALWAYS delegate to orchestrator

2. === DELEGATION PROTOCOL (MANDATORY) ===
   - EMBED full user story in task prompt
   - Do NOT reference external files like 'See docs/BACKLOG_STORIES/file.md'
   - Include: functional requirements, acceptance criteria, tech constraints, out of scope
   - Prevents file access issues when subagents work in git worktrees

3. === PROGRESS MONITORING (MANDATORY) ===
   - Check progress every 30 minutes after delegation
   - Report status to human every 30 minutes
   - Flag blockers immediately
   - Verify orchestrator completed work before updating BACKLOG.md

4. === PROJECT-SPECIFIC KNOWLEDGE ===
   - Turnstile bot protection: live on web, NOT on Android
   - Android min SDK 26, embedding provider: Ollama
   - Open PRs: #164, #167-#170
   - Web app is live - stability > velocity

TESTING:
- JSON syntax validation via pre-commit
- Manual verification: agent loads correctly
- Behavioral test: verify agent follows delegation protocol

DELIVERABLES:
1. Branch created
2. Changes committed (opencode.json + CLAUDE.md deletion only)
3. Global config cleaned up locally (NOT committed)
4. PR opened with descriptive title and body
5. CI passing
6. Report back with PR URL
```

---

## ✅ Approval Checklist

Before I delegate these tasks to the orchestrator, please confirm:

- [ ] **BITB-014 scope approved** - Fix migration pipeline bug (P0)
- [ ] **BITB-015 scope approved** - Consolidate agent configuration (P1)
- [ ] **Delegation approach approved** - Both stories in parallel (Option A)
- [ ] **User stories reviewed** - Both stories documented in `docs/BACKLOG_STORIES/`
- [ ] **BACKLOG.md updated** - Both stories added to backlog

---

## 🚦 Next Steps After Approval

1. **I will delegate** both tasks to orchestrator using the prompts above
2. **I will monitor** progress every 30 minutes
3. **I will report** status updates to you
4. **I will update** BACKLOG.md when PRs are opened
5. **I will verify** both PRs pass CI before reporting completion

---

## ❓ Questions for You

1. **Approve both stories?** (BITB-014 and BITB-015)
2. **Delegate in parallel or sequentially?** (Recommend parallel)
3. **Any changes to scope or acceptance criteria?**

---

**Ready to execute pending your approval.**
