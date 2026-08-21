# BITB-102: PWA Offline Shell — Versioned Service Worker for the App Shell + Scripture GETs

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (1 day)
**Created:** 2026-08-07
**Split from:** BITB-084 Part C, per that story's own explicit guidance ("if Part C threatens
the timebox, split it out — Parts A+B alone deliver installability"). BITB-084 (Parts A, B, D —
manifest, iOS safe areas, `/app` iOS install instructions) shipped without this.

## User Story

**As an** iPhone or Android user who has installed Vox Quieta to their home screen, **I want** the
app shell to load instantly and show a friendly message instead of a browser error when I have no
connection, **so that** the installed app feels like an app, not a bookmark that breaks offline.

## Why

BITB-084 made Vox Quieta installable (manifest, icons, safe areas) but shipped with no service
worker. Everything that makes the *installed* experience feel first-class when a connection drops
or is slow is still missing:

- Opening the installed app with no signal shows Safari/Chrome's native offline error page, not
  anything Vox Quieta controls.
- There is no shell caching, so every cold open of the installed app re-fetches the same static
  assets a normal repeat visitor's browser cache would already have warm.
- `frontend/public/` has no `sw.js` and nothing registers one.

This was deliberately deferred out of BITB-084 rather than rushed, because the story itself calls
out cache-versioning as "the single biggest risk in Part C — an un-versioned service worker is how
you ship an unfixable bug," and a same-day PWA-installability story was the wrong place to also
get a cache-invalidation strategy right under time pressure.

## Scope

Carried over verbatim from BITB-084 Part C:

- Cache the app shell and static assets only, **never** `POST /api/v1/chat/stream` or any response
  carrying/consuming `X-Turnstile-Token` (single-use — see
  `android/.../interceptors/TurnstileInterceptor.kt` for why replay is a correctness bug, not a
  feature).
- Offline fallback page telling the user chat needs a connection, localized (reuse the `App.*` /
  a new namespace, in all 11 locales).
- Scripture `GET` endpoints (`/api/v1/scripture/translations`, `/scripture/book-names`,
  `/scripture/chapter/{book}/{chapter}`) are safe to cache stale-while-revalidate and are the
  highest-value offline win.
- A cache-busting/versioning story tied to the build (e.g. a build-id-suffixed cache name), so a
  deploy cannot leave an installed user pinned to a stale shell indefinitely.

## Acceptance Criteria

- [ ] Offline (airplane mode) opening the installed app shows the localized offline fallback, not
      a browser error page.
- [ ] Chat requests (`POST /api/v1/chat/stream`) are never served from cache and never cached.
- [ ] No response carrying or consuming `X-Turnstile-Token` is cached.
- [ ] Scripture `GET` endpoints are cached stale-while-revalidate.
- [ ] A new deploy invalidates the shell cache — a user with the app open gets the new build on
      next launch without manually clearing site data. Prove this with a test that changes the
      build id and asserts the old cache name is evicted.
- [ ] Registering the service worker does not regress Lighthouse/PWA installability criteria
      already met by BITB-084.

## Tests to Add

- Service-worker unit/integration tests: cache-name changes with the build id; a `POST` to
  `/api/v1/chat/stream` bypasses the cache; a response containing `X-Turnstile-Token` is never
  written to cache.
- Playwright (`frontend/e2e/`) offline-fallback assertion — `frontend/playwright.config.ts`
  already exists and supports offline emulation.
- i18n parity test coverage for any new offline-fallback copy namespace, across all 11 locales
  (the existing generic `frontend/src/test/translations.test.ts` key-parity check already covers
  this once the keys exist).

## Out of Scope

- Web Push (see BITB-084's Out of Scope — still no push anywhere in the product).
- Offline *chat* — the answer comes from an LLM over the network; there is nothing to cache.
- Anything already shipped in BITB-084 (manifest, icons, `viewportFit`, `appleWebApp`, the `/app`
  iOS branch).

## Related

- **BITB-084** — installability, safe areas, and the `/app` iOS funnel (shipped; this story is its
  Part C carve-out).
- **Icebox → "Offline Mode (Web): Service worker for offline scripture access"** — this is the
  concrete version of that idea; remove it from the Icebox once this ships.
