# PR #68: Security Dependency Updates

**Status:** In Progress
**PR URL:** <https://github.com/zioalex/getinspiredbythebible/pull/68>
**Started:** 2026-02-05

## Summary

Updates npm dependencies to address security vulnerabilities reported by Dependabot.

## Vulnerabilities Being Fixed

| Severity | Package | Issue |
|----------|---------|-------|
| **Critical** | vitest | Remote Code Execution (CVE) |
| **High** | next | HTTP request deserialization DoS |
| **High** | next | Image Optimizer DoS |

## Changes

- `next`: 14.2.35 → 15.5.11
- `react`/`react-dom`: 18.3.1 → 19.0.0 (required for Next.js 15)
- `vitest`: 2.1.8 → 2.1.9
- `eslint-config-next`: 14.2.35 → 15.5.11

## Breaking Changes

This is a **major version upgrade** for:

- Next.js (14 → 15)
- React (18 → 19)

## Tasks

- [x] Checkout PR branch
- [x] Review code changes
- [x] Run `npm install` in frontend/
- [x] Run `npm run build` to verify build works
- [x] Run `npm run lint` to check for issues
- [x] Run unit tests (46 tests pass)
- [ ] Test the application locally
- [x] Verify CI/CD pipelines pass
- [x] Check for any React 19 breaking changes in components
- [x] Document any issues found
- [ ] Merge PR if all checks pass

## Progress Log

### 2026-02-05

- Created tracking document
- Starting analysis...

### 2026-02-06

- Checked out branch `fix/security-vulnerabilities`
- Verified package.json changes match documented updates
- `npm install` completed with 5 moderate severity warnings (esbuild via vitest)
- `npm run build` succeeds with warning about @next/swc version mismatch (15.5.7 vs 15.5.11)
  - This is a cosmetic warning, build completes successfully
- `npm run lint` passes with no warnings or errors
- `npm run type-check` passes
- `npm run test:unit` passes - all 46 tests pass
- **Found branch was 47 commits behind main** - CI failing due to missing deployment fixes
- **Rebased branch on main** - Cherry-picked security commit onto current main
  - Force-pushed to update PR #68
  - Terraform workflow fix commit was already in main (empty after rebase)
- ✅ All CI workflows passed after rebase:
  - Pre-Commit Validation: 49s
  - Build and Deploy to Azure: 4m45s
  - CI/CD - Test Application: 7m30s

## Notes

Remaining moderate vulnerabilities (not addressed in this PR):

- esbuild (via vitest) - needs vitest 4.x
- eslint - needs 9.x

## Issues Found

### Blocking Issues

1. ~~**Branch is 47 commits behind main**~~ - ✅ RESOLVED
   - Rebased branch on main (2026-02-06)
   - Force-pushed to update PR #68

### CI Pipeline Status (as of 2026-02-06)

| Workflow | Status |
|----------|--------|
| Pre-Commit Validation | ✅ Passed |
| Terraform Infrastructure | ✅ Passed |
| CI/CD - Test Application | ✅ Passed |
| Build and Deploy to Azure | ✅ Passed (after rebase) |

### Minor Issues (non-blocking)

1. **@next/swc version mismatch warning** - Build shows warning about swc version 15.5.7 vs Next.js 15.5.11
   - This is cosmetic; build completes successfully
   - May be related to npm cache or transitive dependencies

2. **`next lint` deprecation notice** - Next.js 16 will remove this; should migrate to ESLint CLI
   - Not blocking for this PR

### Additional Changes in PR

This PR includes changes beyond security updates:

- `fix(ci): Add permissions for Terraform workflow PR comments`
- Various component refactoring (page.tsx, ChatMessage.tsx, api.ts)
- Terraform configuration changes
- Removed ChurchFinderInlinePrompt component
- Makefile changes

**Recommendation:** These additional changes should ideally be in separate PRs per CLAUDE.md
workflow rules. However, they appear functional and don't break the build.

## Next Steps

1. ~~**Rebase on main**~~ - ✅ Done
2. ~~**Wait for CI to pass**~~ - ✅ All workflows passed
3. **Test locally** - Run the application and verify chat functionality works
4. **Merge PR** - Once local testing confirms functionality
