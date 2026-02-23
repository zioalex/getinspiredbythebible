# PR Conflicts Analysis & Sync Plan

**Date:** 2026-02-23
**Analyzed By:** Product Owner + Orchestrator Agent

---

## Executive Summary

**Critical Finding:** PRs #164, #168, #169, and #170 all branched from `8232baf` (98 commits behind main). Since then, **PR #156 merged a full Android scaffold into main**, making PR #164 redundant and causing cascading conflicts in #168, #169, #170.

**Immediate Actions:**

1. ✅ Merge PR #171 (Turnstile fix) - NO CONFLICTS, CI running
2. ⚠️ Close PR #164 (Android bootstrap) - superseded by PR #156
3. 🔄 Rebase PRs #167, #168, #169, #170 onto main

---

## Detailed PR Status

### ✅ PR #171 — Turnstile Ready Check (READY TO MERGE)

- **Status**: Open, CI running
- **Branch**: `fix/turnstile-ready-check`
- **Mergeable**: ✅ YES
- **Conflicts**: None
- **Behind main**: 0 commits (up to date)
- **CI Status**: Pre-commit ✅, Tests ✅, Security ✅, Build/Integration ⏳
- **Action**: **Merge when CI finishes** (estimated: minutes)
- **Blocks**: Nothing

---

### ⚠️ PR #164 — Android App Bootstrap (CLOSE RECOMMENDED)

- **Status**: Open, CONFLICTING
- **Branch**: `feat/android-app-bootstrap`
- **Mergeable**: ❌ NO
- **Conflicts**: All `android/*` files (add/add with PR #156)
- **Behind main**: 98 commits
- **Root Cause**: PR #156 (`feat: Android app scaffold`) already merged the same Android bootstrap into main at commit `c6c53d5`
- **Action**: **CLOSE THIS PR** — the work is already in main via PR #156
- **Human Decision Required**: Review commit `e2c9157` to verify no unique code is lost
- **Unblocks**: PRs #169, #170 (which are stacked on this)

---

### 🔄 PR #167 — ESLint 9 Migration (NEEDS REBASE)

- **Status**: Open, CONFLICTING
- **Branch**: `fix/eslint9-flat-config` (worktree: `/home/asurace/github/worktree-eslint`)
- **Mergeable**: ❌ NO
- **Conflicts**:
  - `.pre-commit-config.yaml` (ESLint hook entry)
  - `frontend/eslint.config.mjs` (add/add)
  - `frontend/package.json` (version skew)
  - `frontend/package-lock.json`
- **Behind main**: 98 commits
- **Action**:
  1. Rebase onto main
  2. Keep main's newer package versions
  3. Keep branch's flat ESLint config
  4. Reconcile `.pre-commit-config.yaml`
- **Blocks**: Nothing (standalone)

---

### 🔄 PR #168 — Android Secrets Scan CI (NEEDS REBASE)

- **Status**: Open, CONFLICTING
- **Branch**: `feat/android-ci-secrets-scan` (worktree: `/home/asurace/github/worktree-android-secrets`)
- **Mergeable**: ❌ NO
- **Conflicts**:
  - `.github/workflows/android-ci.yml` (add/add — branch has minimal workflow, main has full workflow)
- **Behind main**: 98 commits
- **Action**:
  1. Rebase onto main
  2. Manually merge `secrets-scan` job into main's existing `android-ci.yml`
  3. Keep main's structure (run-name, workflow_dispatch, existing jobs)
  4. Add the `secrets-scan` job alongside existing jobs
- **Blocks**: Nothing (standalone)

---

### 🔄 PR #169 — Android OWASP Dependency Check (NEEDS REBASE)

- **Status**: Open, CONFLICTING
- **Branch**: `feat/android-ci-dependency-check` (worktree: `/home/asurace/github/worktree-android-depcheck`)
- **Mergeable**: ❌ NO
- **Conflicts**:
  - `android/build.gradle.kts` (add/add — plugin differences)
  - `android/gradle.properties` (add/add)
  - `android/gradle/libs.versions.toml` (add/add)
  - `android/gradlew` (add/add)
  - `android/settings.gradle.kts` (add/add)
- **Behind main**: 98 commits
- **Stack Dependency**: Includes commit `e2c9157` from PR #164
- **Action**:
  1. **Wait for PR #164 to be closed**
  2. Rebase onto main
  3. Cherry-pick only OWASP-specific changes:
     - `dependency-check` plugin in `build.gradle.kts`
     - Suppression file
     - OWASP CI job
- **Blocks**: PR #170 (which is stacked on this)

---

### 🔄 PR #170 — Android APK Security Check (NEEDS REBASE)

- **Status**: Open, CONFLICTING
- **Branch**: `feat/android-ci-apk-security` (worktree: `/home/asurace/github/worktree-android-apksec`)
- **Mergeable**: ❌ NO
- **Conflicts**: Same as PR #169 plus additional Android source files
- **Behind main**: 98 commits
- **Stack Dependency**: Includes commits from PR #164 (`e2c9157`) and PR #169 (`35092ad`)
- **Action**:
  1. **Wait for PR #164 to be closed**
  2. **Wait for PR #169 to be rebased and merged**
  3. Rebase onto main
  4. Cherry-pick only APK security additions:
     - `AndroidManifest.xml` security flags
     - `network_security_config.xml`
     - `apk-security-check` CI job
- **Blocks**: Nothing (end of chain)

---

### ✅ PR #68 — Security Updates (ALREADY MERGED)

- **Status**: Merged
- **Action**: None required

---

## Dependency Map

```
main (current)
│
├── PR #171 (turnstile) ────────────────────→ ✅ MERGE NOW (no conflicts)
│
├── PR #156 (android scaffold) ─────────────→ ✅ ALREADY MERGED
│
├── PR #164 (android bootstrap) ────────────→ ⚠️  CLOSE (superseded by #156)
│   │
│   ├── PR #169 (OWASP) ────────────────────→ 🔄 REBASE (after #164 closed)
│   │   │
│   │   └── PR #170 (APK security) ─────────→ 🔄 REBASE (after #169 merged)
│   │
│   └── (conflicts with main's android/ files)
│
├── PR #167 (eslint9) ──────────────────────→ 🔄 REBASE (standalone)
│
└── PR #168 (secrets scan) ─────────────────→ 🔄 REBASE (standalone)
```

---

## Recommended Merge Order

| Step | PR | Action | Estimated Time | Blocker? |
|------|-------|--------|----------------|----------|
| 1 | **#171** | Merge when CI passes | ~5 min | None |
| 2 | **#164** | Close (or cherry-pick if unique code exists) | ~10 min | Blocks #169, #170 |
| 3 | **#167** | Rebase, resolve conflicts, test, merge | ~30 min | None |
| 4 | **#168** | Rebase, merge secrets job into android-ci.yml | ~20 min | None |
| 5 | **#169** | Rebase, cherry-pick OWASP changes, test, merge | ~30 min | Blocked by #164 |
| 6 | **#170** | Rebase, cherry-pick APK security, test, merge | ~30 min | Blocked by #169 |

**Total estimated time:** ~2 hours

---

## Action Plan for Human

### Phase 1: Immediate (Next 15 minutes)

1. ✅ **Check CI for PR #171** — if green, merge immediately
2. ⚠️ **Review PR #164 commit `e2c9157`**:
   - Compare with PR #156's merged code
   - Decision: Close PR #164 or identify unique code to preserve

### Phase 2: Rebase Standalone PRs (Next 1 hour)

**Option A: Delegate to Orchestrator**

```
Orchestrator: Rebase PR #167 onto main, resolve conflicts, run tests, create new PR if needed
Orchestrator: Rebase PR #168 onto main, merge secrets-scan job into android-ci.yml
```

**Option B: Manual**
Use worktrees at:

- `/home/asurace/github/worktree-eslint`
- `/home/asurace/github/worktree-android-secrets`

### Phase 3: Rebase Stacked Android PRs (Next 1 hour)

**After PR #164 is closed:**

1. **PR #169 (OWASP)**:

   ```
   cd /home/asurace/github/worktree-android-depcheck
   git fetch origin
   git rebase origin/main
   # Resolve conflicts, keeping only OWASP-specific changes
   ```

2. **PR #170 (APK Security)**:

   ```
   cd /home/asurace/github/worktree-android-apksec
   git fetch origin
   git rebase origin/main
   # Resolve conflicts, keeping only APK security changes
   ```

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| PR #164 has unique code lost if closed | Medium | Human review commit `e2c9157` before closing |
| Rebase conflicts in #167, #168, #169, #170 | Low | Use worktrees, test thoroughly |
| CI failures after rebase | Low | Run `make pre-commit` and full test suite |
| Stacked PRs (#169, #170) break during rebase | Medium | Rebase one at a time, test after each |

---

## Next Steps

**Human Decision Required:**

1. Do you want to merge PR #171 now (if CI is green)?
2. Should I close PR #164, or do you want to review it first?
3. Should I delegate the rebases to the orchestrator, or do you prefer to handle them manually?

Let me know how you'd like to proceed! 🚀
