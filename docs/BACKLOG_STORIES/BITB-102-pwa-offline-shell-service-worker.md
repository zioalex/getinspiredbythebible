# BITB-102: PWA Offline Shell — Versioned Service Worker for the App Shell + Scripture GETs

**Status:** ✅ Done (2026-09-12)
**Priority:** P2
**Size:** M (1 day)
**Created:** 2026-08-07
**Completed:** 2026-09-12
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

- [x] Offline (airplane mode) opening the installed app shows the localized offline fallback, not
      a browser error page.
- [x] Chat requests (`POST /api/v1/chat/stream`) are never served from cache and never cached.
- [x] No response carrying or consuming `X-Turnstile-Token` is cached. Implemented structurally,
      not by inspecting the outgoing token: (1) the `fetch` handler returns before any cache code
      runs for any non-GET request, so POSTs (chat/feedback/church-search) are never looked up or
      written regardless of headers; (2) the scripture cache is keyed by the bare `request.url`
      **string** (never the `Request` object) on both read and write, so a Turnstile-token-bearing
      GET (`searchScripture`/`getVerse`/`getChapter` all attach the token via `api.ts`'s
      `getHeaders()`) never has a way to persist those headers into cache storage; (3) a
      response-side `isCacheableResponse` guard additionally refuses to cache anything with a
      `Vary: X-Turnstile-Token` header or an echoed-back `X-Turnstile-Token` response header, as a
      second line of defense. See `frontend/src/test/sw.test.ts`.
- [x] Scripture `GET` endpoints are cached stale-while-revalidate.
- [x] A new deploy invalidates the shell cache — a user with the app open gets the new build on
      next launch without manually clearing site data. Proven by `frontend/src/test/sw.test.ts`,
      which runs the shipped `public/sw.js` twice via a shared fake `CacheStorage` — once at
      `?v=build-A`, once at `?v=build-B` — and asserts `vq-shell-build-A` is evicted on the second
      worker's `activate` while `vq-shell-build-B` and the un-versioned `vq-scripture-v1` survive.
- [x] Registering the service worker does not regress Lighthouse/PWA installability criteria
      already met by BITB-084: `src/app/manifest.test.ts` is unmodified and still green, and the
      service worker's `fetch` handler never intercepts `/manifest.webmanifest` (it falls through
      the allowlist/denylist checks untouched to the network).

## Tests to Add

Shipped:

- `frontend/src/test/swHarness.ts` — loads and executes the actual shipped `public/sw.js` inside
  the test process (via `new Function(...)` against a fake `self`/`CacheStorage`/`fetch`), so tests
  exercise real service-worker behaviour rather than a reimplementation.
- `frontend/src/test/sw.test.ts` — cache naming and the `?v=` → `vq-shell-<id>` contract; the
  deploy-invalidation proof described above; POST bypass for chat/feedback/church-search
  (including a "poisoning" test that pre-seeds a cache entry and confirms it's still not served to
  a POST); the `/api/v1/chat` GET denylist; Turnstile-token cache-key discipline (bare URL string,
  `Vary`/echoed-header guards); `challenges.cloudflare.com` passthrough; scripture
  stale-while-revalidate (cold/warm, network-reject fallback, `search` exclusion, 500 exclusion,
  FIFO trim at `SCRIPTURE_CACHE_MAX_ENTRIES`); the offline-fallback precache and navigation
  fallback behaviour; `manifest.webmanifest` passthrough; static-asset cache-first behaviour.
- `frontend/scripts/generate-build-info.test.mjs` — `resolveBuildId` sanitization/fallback.
- `frontend/scripts/generate-offline-page.test.mjs` — `buildOfflineHtml` locale coverage, the
  `</script>`-escaping requirement, and the self-containment invariant (no external `src`/`href`).
- `frontend/src/lib/registerServiceWorker.test.ts` — production-only gating, fail-closed behaviour
  on a missing/invalid `build-info.json`, non-production unregister path, and the
  `reportClientError` failure path.
- `frontend/src/app/[locale]/providers.test.tsx` — asserts `ServiceWorkerRegistrar` is rendered.
- `frontend/src/test/translations.test.ts` — `Offline` added to the required-namespace list, so
  the existing key-parity/no-empty-value checks now cover it across all 11 locales.
- `frontend/e2e/offline-shell.spec.ts` — Playwright offline-fallback assertion (not CI-gated; needs
  a production build since registration is production-only — see file header).

## Design Decisions

- **Classic (non-module) service worker.** `public/sw.js` is registered without
  `{ type: "module" }` for broad Safari compatibility.
- **No `skipWaiting()`.** A new worker version activates once every client tied to the old worker
  has closed (i.e. "on next launch"), not mid-session out from under an in-flight chat stream.
  `clients.claim()` in `activate` still lets a newly-activated worker take control of open clients
  immediately rather than waiting for the next navigation.
- **Offline fallback is a generated, self-contained static file, not a Next.js route.** A
  `[locale]/offline` route would need `_next/static/...` chunks to render — exactly what's
  unreachable when offline. `scripts/generate-offline-page.mjs` inlines CSS/SVG/JS and all 11
  locales' strings so the file works standalone from the shell cache.
- **The scripture cache is not build-id-versioned.** `vq-scripture-v1` is hand-bumped only and
  deliberately survives deploys (unlike `vq-shell-<buildId>`, which is evicted every deploy) — a
  deploy shouldn't cold-start the offline-scripture win the whole feature exists for.
- **`/api/v1/scripture/search` is excluded from caching.** Unbounded query cardinality makes it a
  poor cache candidate and a low offline-value one compared to translations/book-names/chapter/verse.

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
