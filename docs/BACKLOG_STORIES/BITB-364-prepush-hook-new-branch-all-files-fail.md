---
id: BITB-364
status: todo
priority: P3
size: S
created: 2026-11-26
---

# BITB-364: pre-push Hook Auto-Fixes Unrelated Files and Fails on New-Branch Pushes

**Filed from:** BITB-363 (observed live while pushing its branch, 2026-11-26).

## Problem

Pushing a **new branch** with the installed pre-push git hook
(`pre-commit install --hook-type pre-push`) does not work on the current
`main`:

1. pre-commit's pre-push hook cannot compute a push range for a ref that
   does not exist on the remote yet, and falls back to scanning **all
   files**.
2. Several pre-push-stage hooks **write** (`prettier-yaml` with write
   semantics, the frontend `prettier`, `markdownlint --fix`). Over the
   all-files set they silently rewrote **ten unrelated files** in the
   pusher's tree (observed: `CHANGELOG.md`,
   `api/golden_set/test_cases/interpretation.yaml`, four
   `docs/BACKLOG_STORIES/BITB-*.md`, two `frontend/public/legal/*.md`,
   `frontend/src/lib/api.ts`, `scripts/env-manifest.yaml`).
3. `yamllint` (line-length 120) then **fails on prettier's own output**:
   joining `interpretation.yaml`'s folded Hindi scalars produced lines of
   126/138/137 chars. It also fails on the pre-existing
   `.github/workflows/test_update.yml:443` (123 chars).
4. One run crashed mid-chain with a node ESM error
   (`ModuleJob._link`), leaving the rewrites half-applied.

Net effect: the first push of any feature branch leaves the working tree
dirty with changes the pusher never made, blocks the push, and the only
path forward is `git checkout -- .` plus a hooks-bypassed push (what the
BITB-363 session did) — losing the pre-push gate exactly when it matters
(a fresh branch).

Note: CI is unaffected — its Pre-Commit Hooks job runs the commit-stage
hooks (`pre-commit run --all-files`), which do not include the writing
pre-push-stage hooks. This is a developer-workstation-only failure, which
is also why it has gone unnoticed.

## Acceptance criteria

- [ ] A new-branch push runs the pre-push hooks against a sane file set
      (changed files only, or all-files without the write-mode hooks), and
      leaves the tree clean if it fails
- [ ] The prettier-vs-yamllint contradiction is resolved for long
      non-breakable scalars (`interpretation.yaml`) — either exclude the
      generated golden-set data from the auto-fixing hooks or teach
      yamllint to ignore those lines (config change, not data change)
- [ ] The pre-existing `.github/workflows/test_update.yml:443` line-length
      violation is fixed or ignored
- [ ] Reproduce before/after in the story (push a scratch branch with the
      hook installed) and record the outcome

## Out of scope

- The commit-stage hooks (they pass on main and in CI)

## References

- Observed 2026-11-26 pushing `feature/llama-cpp-provider-config` (BITB-363):
  two blocked pushes, the ten-file rewrite list, and the yamllint output
  above
- BITB-243 (the pre-push stage split that made these hooks push-time-only)
