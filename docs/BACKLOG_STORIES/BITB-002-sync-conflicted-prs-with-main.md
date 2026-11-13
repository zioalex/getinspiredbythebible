---
id: BITB-002
status: in-progress
priority: P1
size: M
rank: 790
prs: [171]
---

# BITB-002: Sync Conflicted PRs with Main

**Status note:** (PR #171 merged, ready to start)

**As a** developer,
**I want** all open PRs to be conflict-free and up-to-date with main,
**so that** we can review and merge them without manual intervention.

**Acceptance Criteria:**

- [ ] PR #167 (ESLint 9) rebased on latest main, conflicts resolved
- [ ] PR #168 (Secrets scan CI) rebased on latest main, conflicts resolved
- [ ] PR #169 (OWASP dependency check) rebased on latest main, conflicts resolved
- [ ] PR #170 (APK security flags) rebased on latest main, conflicts resolved
- [ ] All rebased PRs pass CI checks
- [ ] Tracking document moved to `docs/DONE/`

**Tech Constraints:**

- Must maintain git history (use rebase, not merge)
- Must preserve existing commit messages and authorship
- Must run `make pre-commit` before pushing

**Dependencies:**

- ✅ PR #171 merged (unblocked)
- PR #170 depends on PR #169

**Tracking Doc:** `docs/WIP/PR-CONFLICTS-AND-SYNC-PLAN.md`
