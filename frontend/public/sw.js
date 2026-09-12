/**
 * Vox Quieta PWA offline shell — versioned service worker (BITB-102).
 *
 * === Build-id contract ===
 * This is a CLASSIC (non-module) script, registered by
 * `src/lib/registerServiceWorker.ts` as `/sw.js?v=<buildId>`, where
 * `<buildId>` comes from `public/build-info.json` (written at build time by
 * `scripts/generate-build-info.mjs`). We read the `?v=` query param off our
 * own script URL at install time to derive `BUILD_ID`. Changing the build id
 * on every deploy renames `SHELL_CACHE`, so a stale shell cache from a
 * previous deploy is deleted in `activate` instead of silently lingering
 * forever on an installed user's device.
 *
 * === No skipWaiting() ===
 * We deliberately do NOT call `self.skipWaiting()` in `install`. A new
 * service worker version therefore stays "waiting" until every open client
 * (tab/PWA window) referencing the *old* worker is closed, at which point the
 * browser activates the new one automatically. This matches the acceptance
 * criterion ("a deploy invalidates the shell cache ... on next launch") and
 * avoids swapping the worker out from under a page that's mid-session
 * (e.g. an in-flight chat stream). `clients.claim()` IS called in `activate`
 * so that once a new worker does take over, it controls open clients
 * immediately rather than waiting for the next navigation.
 *
 * === HTML is never cached ===
 * Navigation requests are network-first and, on success, the response is
 * NOT written to any cache. A cached HTML document from a previous deploy
 * would reference `_next/static/<old-hash>/...` chunks that `activate` has
 * already evicted, producing a broken page instead of a clean offline
 * fallback. Only on network failure do we serve the precached
 * `/offline.html` (a fully self-contained, generated file — see
 * `scripts/generate-offline-page.mjs` — that needs no `_next/static` assets).
 *
 * === Non-GET requests bypass all cache code ===
 * `fetch` returns immediately (no `respondWith` call) for any non-GET
 * request, before any URL/path inspection happens. This is what makes chat
 * POSTs (`/api/v1/chat`, `/api/v1/chat/stream`), feedback POSTs, and
 * church-search POSTs structurally untouchable by the cache — they're never
 * looked up, never written, regardless of headers. Combined with keying the
 * scripture cache by bare URL string (never the `Request` object), a
 * Turnstile-token-bearing request never has a way to leak its headers into
 * cache storage.
 *
 * === Kill switch ===
 * To disable this service worker org-wide, ship a replacement `sw.js` whose
 * `install` handler calls `self.registration.unregister()` (and skips
 * everything else). Existing installed workers will pick it up like any
 * other update and remove themselves.
 */

const BUILD_ID =
  new URL(self.location.href).searchParams.get("v") || "unversioned";

const SHELL_CACHE = "vq-shell-" + BUILD_ID;
const SCRIPTURE_CACHE = "vq-scripture-v1"; // hand-bumped only — survives deploys
const MANAGED_CACHES = [SHELL_CACHE, SCRIPTURE_CACHE];
const CACHE_PREFIX = "vq-";

const OFFLINE_URL = "/offline.html";
// Keep the install failure-surface tiny: cache.addAll is all-or-nothing, so
// precache only the one asset install must not fail without.
const PRECACHE = [OFFLINE_URL];

// Matched on pathname only (origin-agnostic — the API may be cross-origin
// relative to the frontend).
const SCRIPTURE_PATH_ALLOWLIST = [
  "/api/v1/scripture/translations",
  "/api/v1/scripture/book-names",
  "/api/v1/scripture/chapter/",
  "/api/v1/scripture/verse/",
];

const STATIC_PATH_PREFIXES = ["/_next/static/", "/icons/"];
const STATIC_SAME_ORIGIN_PATHS = [
  "/icon.svg",
  "/apple-touch-icon.png",
  "/app-icon.png",
];

const SCRIPTURE_CACHE_MAX_ENTRIES = 100;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(PRECACHE)),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter(
              (name) =>
                name.startsWith(CACHE_PREFIX) &&
                !MANAGED_CACHES.includes(name),
            )
            .map((name) => caches.delete(name)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

/**
 * Whether a network Response is safe to persist in a cache: a plain 200, of
 * an opaque-free type (basic same-origin or cors cross-origin — never
 * "opaque", which we can't inspect), and — crucially — carrying no trace of
 * the single-use Turnstile token. `Vary: X-Turnstile-Token` would mean this
 * response's content depends on that header (so caching it under a bare URL
 * key would be wrong), and echoing the header back would mean the token
 * itself is sitting in the cached response.
 */
function isCacheableResponse(res) {
  return Boolean(
    res &&
      res.status === 200 &&
      (res.type === "basic" || res.type === "cors") &&
      !/x-turnstile-token/i.test(res.headers.get("Vary") || "") &&
      !res.headers.has("X-Turnstile-Token"),
  );
}

function matchesScriptureAllowlist(pathname) {
  return SCRIPTURE_PATH_ALLOWLIST.some((prefix) => pathname.startsWith(prefix));
}

function matchesStaticAsset(pathname) {
  return (
    STATIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix)) ||
    STATIC_SAME_ORIGIN_PATHS.includes(pathname)
  );
}

/** Trim a cache to at most `max` entries, oldest first (FIFO by insertion order). */
async function trimCache(cache, max) {
  const keys = await cache.keys();
  const excess = keys.length - max;
  if (excess <= 0) return;
  for (let i = 0; i < excess; i++) {
    await cache.delete(keys[i]);
  }
}

/**
 * Stale-while-revalidate for a scripture allowlist GET. Cache key discipline:
 * both lookup and write use `request.url` (a plain string) — never the
 * `Request` object — so a token-bearing request's headers never end up
 * inside cache storage, regardless of `isCacheableResponse`.
 */
async function handleScriptureRequest(event, request) {
  const cache = await caches.open(SCRIPTURE_CACHE);
  const cached = await cache.match(request.url);

  const revalidate = fetch(request)
    .then(async (response) => {
      if (isCacheableResponse(response)) {
        await cache.put(request.url, response.clone());
        await trimCache(cache, SCRIPTURE_CACHE_MAX_ENTRIES);
      }
      return response;
    })
    .catch(() => undefined);

  if (cached) {
    // Serve the stale copy immediately; let the revalidation finish in the
    // background so `waitUntil` keeps the SW alive for it even on a cache hit.
    event.waitUntil(revalidate);
    return cached;
  }

  // No cache entry: fall through to the network, still updating the cache.
  const response = await revalidate;
  if (response) return response;
  return Response.error();
}

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // 1. Non-GET requests are never inspected further, let alone cached. This
  // alone makes chat/feedback/church-search POSTs structurally untouchable.
  if (request.method !== "GET") return;

  let url;
  try {
    url = new URL(request.url);
  } catch {
    return;
  }

  // 2. Only intercept http(s) — leave chrome-extension:, etc. alone.
  if (url.protocol !== "http:" && url.protocol !== "https:") return;

  // 3. Hard denylist: nothing under the turnstile-gated chat namespace is
  // ever cached, including the GET /api/v1/chat/verse/... endpoint.
  if (url.pathname.startsWith("/api/v1/chat")) return;

  // 4. Never intercept the Turnstile widget script itself.
  if (url.hostname === "challenges.cloudflare.com") return;

  // 5. Navigation requests: network-first, offline fallback on failure.
  // Deliberately never cache the HTML response on success (see file header).
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(SHELL_CACHE);
        const offline = await cache.match(OFFLINE_URL);
        return offline || Response.error();
      }),
    );
    return;
  }

  // 6. Same-origin static assets: cache-first.
  if (url.origin === self.location.origin && matchesStaticAsset(url.pathname)) {
    event.respondWith(
      caches.open(SHELL_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        const response = await fetch(request);
        if (response && response.ok && response.status === 200) {
          await cache.put(request, response.clone());
        }
        return response;
      }),
    );
    return;
  }

  // 7. Scripture allowlist GETs: stale-while-revalidate.
  if (matchesScriptureAllowlist(url.pathname)) {
    event.respondWith(handleScriptureRequest(event, request));
    return;
  }

  // 8. Everything else (/health, /config, /api/v1/scripture/search, fonts,
  // analytics, manifest.webmanifest, ...) is left completely untouched.
});
