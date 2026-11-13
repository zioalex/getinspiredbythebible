# BITB-157: Wire `NEXT_PUBLIC_DONATE_URL` Into Docker Compose / Dockerfile / Azure Deploy

**Status:** 🚧 In Progress
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

- [x] Setting `NEXT_PUBLIC_DONATE_URL` in `.env.local`/`.env.dev` changes the link under
      `make docker-up` / `make docker-up-dev` without a source edit
- [x] `azure-deploy.yml` passes the var through to the production build
- [x] AC3 (retargeted): the donate URL is now composed in `frontend/src/lib/donateUrl.ts`
      (BITB-168 refactor moved it out of `Footer.tsx`); its header comment already states the var is
      env-driven with a Ko-fi fallback
- [x] `scripts/env-manifest.yaml`'s `NEXT_PUBLIC_DONATE_URL` entry's `required_in` reconsidered
      now that it can actually be required somewhere (currently `none`)

## Implementation Notes (2026-10-08)

- `docker-compose.dev.yml`'s `frontend` service builds the production stage (no `target: deps`), so a
  runtime `environment:` entry would do nothing; the var is passed via `build.args` instead. Same for
  `docker-compose.prod.yml`. `docker-compose.yml` (dev-server `deps` target) forwards it at runtime.
- `azure-deploy.yml` sources it from the optional repo variable `NEXT_PUBLIC_DONATE_URL`
  (not a secret; unset => empty => Ko-fi fallback).
- `env-manifest.yaml` `required_in` set to `local` (compose forwards it; Terraform does not, so
  `remote`/`both` would fail `validate-env`).
- Tests: `api/tests/test_donate_url_wiring.py`, `frontend/src/lib/donateUrl.test.ts`.

Done pending PR merge.

## Related

- BITB-074 — the story this is deferred from (PR #1084)
- `frontend/src/components/Footer.tsx`, `docker-compose.yml`, `frontend/Dockerfile`,
  `.github/workflows/azure-deploy.yml`, `scripts/env-manifest.yaml`
