---
id: BITB-323
status: todo
priority: P3
size: S
created: 2026-11-16
---

# BITB-323: Keep the Sitemap `lastmod.json` Fresh Automatically

**Follow-up of:** BITB-300.

## Problem

BITB-300 made `<lastmod>` in the sitemap come from git instead of the build time.
`frontend/scripts/generate-lastmod.mjs` writes `frontend/src/generated/lastmod.json`,
and that file is **committed**, because the Docker build context (`frontend/`) has no
`.git` and CI checkouts are shallow (`azure-deploy.yml` uses `fetch-depth: 2`). In that
case the script keeps the committed file unchanged.

So the file only changes when someone runs `npm run build` (or the script) locally with
full history and commits the result. Nothing catches a stale file:

- A PR that edits `about/page.tsx` ships with the old `/about` date.
- After a squash-merge the commit date on `main` differs from the PR-branch date that was
  recorded.
- A local `npm run build` can leave `lastmod.json` modified in the working tree.

## Options

1. In `azure-deploy.yml`, check out with `fetch-depth: 0` (or `git fetch --unshallow`)
   before the frontend Docker build, run the script, and stage the fresh file into the
   build context, the same way `CHANGELOG.md` is staged. The committed file then serves
   only as a fallback.
2. Add a CI freshness check: a full-history job reruns the script and fails if the file
   differs.

Option 1 is preferred because it gives the deployed sitemap the real merge dates without
asking contributors to remember a step.

## Acceptance criteria

- [ ] A deploy after a page change produces that page's new date in the live sitemap
      without a manual commit of `lastmod.json`.
- [ ] Shallow and Docker builds still succeed. The fallback is unchanged.
- [ ] Tests cover the new path. The workflow change is documented in
      `frontend/scripts/generate-lastmod.mjs` and `docs/`.
