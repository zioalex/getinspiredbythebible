# BITB-218: Bump Next.js to 16.4.2 for Critical RCE Advisories

**Status:** ✅ Done — PR #1195, merged 2026-10-23
**Priority:** P0 (critical security advisories; blocks every frontend PR's audit gate)
**Size:** XS
**Created:** 2026-10-23

**As a** maintainer, **I want** the frontend on a Next.js release with no high/critical advisories,
**so that** production is not exposed and the `Security & Dependency Check` job is green on every PR.

## Problem

Three advisories published against `next` 16.0.0–16.4.0 (the lockfile pinned 16.4.0, from BITB-177)
make `node frontend/scripts/npm-audit-gate.mjs` fail on all PRs (first seen on #1191):

- critical: GHSA-2464-fhr4-w9xw, unauthenticated RCE in the Image Optimization API when SVG files are used
- critical: GHSA-673q-mjm6-r5xr, unauthenticated RCE in `use cache` functions returning typed arrays
- high: GHSA-p3m5-59mp-jv5r, DoS in the App Router via Server Actions

## Fix

Bump `next` and `eslint-config-next` to `^16.4.2` and refresh `package-lock.json` with npm.
No allowlist entries added; existing overrides unchanged.

## Acceptance Criteria

- [x] `node scripts/npm-audit-gate.mjs` exits 0
- [x] vitest (73 files / 1393 tests), `tsc --noEmit`, lint (0 errors) and `next build` pass
- [x] CI green
- [ ] Owner check: production deploy after merge runs next 16.4.2

**Note:** the squash commit on `main` (f80eb04) is titled `(BITB-214)` — the story's earlier
number; BITB-214 on `main` is a different story. See BITB-235.

## Follow-ups

- BITB-235 — story IDs collide between concurrent PRs
