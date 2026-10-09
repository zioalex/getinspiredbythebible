# BITB-177: Bump Next.js to clear npm-audit CI gate

**Status:** In review
**Size:** XS
**Created:** 2026-10-09

**As a** maintainer, **I want** the frontend `Security & Dependency Check` job green,
**so that** every PR is not blocked by new high advisories.

## Problem

New high advisories (next SSRF in Image Optimization GHSA-cjq9-62q9-8jv4 for 16.0.0–16.3.7,
sharp <0.35.5 GHSA-wq5f-xc86-pv6w, source-map-js <=1.2.1 GHSA-68fv-2mgg-jv7q) made
`node scripts/npm-audit-gate.mjs` fail on all frontend PRs (#1141, #1135).

## Fix

Bump `next` to `^16.4.0` and refresh the lockfile (sharp 0.35.5, source-map-js 1.2.2 follow).
No allowlist entries added.

## Acceptance criteria

- `node scripts/npm-audit-gate.mjs` exits 0
- vitest, tsc, lint and `next build` pass
