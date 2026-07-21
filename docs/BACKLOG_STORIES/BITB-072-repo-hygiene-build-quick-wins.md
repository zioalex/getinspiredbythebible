# BITB-072: Repo Hygiene & Build Quick Wins (360° Review Compartments)

**Status:** ✅ Done (PR #916, 2026-07-20)
**Priority:** P3
**Size:** S (< 4 hrs)
**Created:** 2026-07-20

**As a** maintainer, **I want** the low-risk optimizations surfaced by the
2026-07-20 360° review shipped as small, independent commits, **so that** the
repo's build hygiene and doc surface improve without any behavioural risk.

## Context

Output of the 360° review (`docs/audits/2026-07-20-360-review.md`), which
reconciled the July adversarial audit against current `main` and swept the
angles it didn't cover (build/packaging, dependency drift, repo hygiene).
Each item below is its own conventional commit so it can be reviewed — or
reverted — independently.

## Acceptance Criteria

- [x] **F4 — root doc rot:** `AGENTS.md.old` / `AGENTS.old.md` deleted;
      `NEXT_STEPS.md`, `MULTILINGUAL_PROGRESS.md`, `TEST_COVERAGE.md` moved to
      `docs/archive/` with an index README; references in BITB-053/054/068
      story files updated.
- [x] **F1 — `.dockerignore`:** added for both `api/` and `frontend/` build
      contexts. Prevents a local `.env` being baked into the api image,
      stops shipping `tests/` + caches, and keeps a local `node_modules`
      out of the frontend build context. Verified CI runs pytest on the host
      and dev compose bind-mounts source, so nothing depends on excluded files.
- [x] **F2 — lint config drift:** `eslint-config-next` bumped `^15.5.20` →
      `^16.2.10` to match `next ^16.2.10`. Verified `npm run lint` (0 errors)
      and `npx tsc --noEmit` clean.
- [x] **Review report** committed to `docs/audits/2026-07-20-360-review.md`.
- [x] Follow-up story **BITB-073** created for the dev/prod requirements split
      (deferred: multi-file blast radius).

## Testing note

Docs, ignore-files, and a lint-tooling version bump — no runtime surface.
Verification = frontend lint + typecheck (run, clean) and grep-verification
that no workflow or runtime path references the newly ignored files.
