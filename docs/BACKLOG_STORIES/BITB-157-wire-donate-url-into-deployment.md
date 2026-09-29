# BITB-157: Wire `NEXT_PUBLIC_DONATE_URL` Into Docker Compose / Dockerfile / Azure Deploy

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-09-17
**Follow-up from:** BITB-074 (PR #1084)

**As** the maintainer, **I want** `NEXT_PUBLIC_DONATE_URL` to actually reach a built/deployed
frontend, **so that** changing the Support-Us donate URL doesn't require editing source code.

## Why

BITB-074 added `NEXT_PUBLIC_DONATE_URL` to `.env.local.example`, `.env.dev.example`,
`.env.production.example`, and `scripts/env-manifest.yaml`, documented as the way to override
the placeholder Ko-fi URL hardcoded as a fallback in `frontend/src/components/Footer.tsx`. The
independent verify pass on that PR found the var is declared but never actually plumbed through:

- `docker-compose.yml`'s `frontend` service only forwards `NEXT_PUBLIC_API_URL` in its
  `environment:` block — the var has no effect under `make docker-up` / `make docker-up-dev`.
- `frontend/Dockerfile` only declares `ARG`/`ENV` for `NEXT_PUBLIC_API_URL` and
  `NEXT_PUBLIC_TURNSTILE_SITE_KEY` — Next.js inlines `NEXT_PUBLIC_*` vars at build time, so a var
  with no `ARG` in the Dockerfile can never reach a production build.
- `.github/workflows/azure-deploy.yml` bakes `NEXT_PUBLIC_API_URL` as a build arg but not this one.

Until this lands, the effective donate URL in every environment is the hardcoded fallback string
in `Footer.tsx`, and the `.env.*.example` comments (corrected by BITB-074's follow-up commit to
say so explicitly) are the honest current state, not the target state.

## Scope

1. `frontend/Dockerfile`: add `ARG NEXT_PUBLIC_DONATE_URL` + `ENV NEXT_PUBLIC_DONATE_URL=...`
   alongside the existing `NEXT_PUBLIC_API_URL` declaration.
2. `docker-compose.yml`: forward `NEXT_PUBLIC_DONATE_URL` in the `frontend` service's
   `environment:` block, same pattern as `NEXT_PUBLIC_API_URL`.
3. `.github/workflows/azure-deploy.yml`: pass `NEXT_PUBLIC_DONATE_URL` as a build arg alongside
   `NEXT_PUBLIC_API_URL` (around line 458), sourced from a repo/environment variable or secret —
   decide which, since this isn't sensitive but should still be centrally settable without a
   code change.
4. Update `frontend/src/components/Footer.tsx`'s comment once this lands (remove the "NOT YET
   wired" caveat).

## Acceptance Criteria

- [ ] Setting `NEXT_PUBLIC_DONATE_URL` in `.env.local`/`.env.dev` changes the link under
      `make docker-up` / `make docker-up-dev` without a source edit
- [ ] `azure-deploy.yml` passes the var through to the production build
- [ ] `Footer.tsx`'s comment updated to reflect the var is now live end-to-end
- [ ] `scripts/env-manifest.yaml`'s `NEXT_PUBLIC_DONATE_URL` entry's `required_in` reconsidered
      now that it can actually be required somewhere (currently `none`)

## Related

- BITB-074 — the story this is deferred from (PR #1084)
- `frontend/src/components/Footer.tsx`, `docker-compose.yml`, `frontend/Dockerfile`,
  `.github/workflows/azure-deploy.yml`, `scripts/env-manifest.yaml`
