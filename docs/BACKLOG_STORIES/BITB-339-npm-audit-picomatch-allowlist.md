---
id: BITB-339
status: done
priority: P1
size: XS
created: 2026-11-17
prs: [1315]
---

# BITB-339: `Security & Dependency Check` Red on `main` (picomatch ReDoS, No Patched Release)

**Bug.** From 2026-11-17 the frontend `npm audit` gate (`frontend/scripts/npm-audit-gate.mjs`) fails on
`main` and on every PR: high advisory
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) (picomatch ReDoS through
single-branch repeated extglobs).

**Root cause / why no upgrade.** The affected range is `<=4.0.7` and 4.0.7 is the newest published
picomatch in every line (2.x, 3.x, 4.x), so no patched version exists. `npm audit`'s suggested
"fixes" (downgrading vitest, `eslint-config-next@14`) are wrong and are not taken.

**Fix.** Add an allowlist entry in `frontend/audit-allowlist.json` (reason + `reviewBy: 2026-12-15`),
the same mechanism the existing mechanism for `braces`. Unlike braces, one copy is in the production
tree (`@parcel/watcher`, the optional file watcher `next-intl` uses at dev/build time), so the
entry's reason records that no request-time path passes user input to picomatch. A test pins the
entry so it cannot be dropped silently, and the gate fails again on `reviewBy`.

## Acceptance criteria

- [x] `node scripts/npm-audit-gate.mjs` exits 0
- [x] Test in `frontend/scripts/npm-audit-gate.test.mjs` pins the allowlist entry
- [ ] Owner step: when a patched picomatch is published, bump the lockfile and delete the allowlist
      entry (the gate fails on 2026-12-15 if it is still there).
