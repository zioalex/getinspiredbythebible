/**
 * BITB-102 — core spec for public/sw.js.
 *
 * Every test here drives the ACTUAL SHIPPED service worker file through
 * `swHarness.ts` (which reads and executes public/sw.js verbatim) — nothing
 * here reimplements the worker's behaviour.
 */
import { readFileSync } from "fs";
import { describe, it, expect, vi } from "vitest";
import {
  loadServiceWorker,
  FakeCacheStorage,
  fakeNetworkResponse,
  SW_PATH,
} from "./swHarness";

const OFFLINE_HTML = "<html><body>You're offline</body></html>";

type Route =
  | Response
  | Response[]
  | Error
  | ((callIndex: number) => Response | Promise<Response>);

function createFetchImpl(routes: Record<string, Route>) {
  const counts: Record<string, number> = {};
  const fn = vi.fn(async (input: any) => {
    const url = typeof input === "string" ? input : input.url;
    const route = routes[url];
    if (route === undefined) {
      throw new Error(`No fetch route configured for ${url}`);
    }
    const n = counts[url] ?? 0;
    counts[url] = n + 1;
    if (route instanceof Error) throw route;
    if (typeof route === "function") return route(n);
    if (Array.isArray(route)) return route[Math.min(n, route.length - 1)];
    return route;
  });
  return fn;
}

function baseRoutes(overrides: Record<string, Route> = {}): Record<string, Route> {
  return {
    "/offline.html": fakeNetworkResponse(OFFLINE_HTML, {
      status: 200,
      headers: { "Content-Type": "text/html" },
    }),
    ...overrides,
  };
}

async function setupInstalledSw(
  buildId: string | undefined,
  routes: Record<string, Route> = {},
  cacheStorage: FakeCacheStorage = new FakeCacheStorage(),
) {
  const fetchImpl = createFetchImpl(baseRoutes(routes));
  const sw = loadServiceWorker({ buildId, cacheStorage, fetchImpl });
  await sw.dispatchInstall();
  await sw.dispatchActivate();
  return { sw, cacheStorage, fetchImpl };
}

function scriptureUrl(path: string) {
  return `https://api.example.test/api/v1/scripture/${path}`;
}

/** True if the mocked fetch was invoked (at least once) for the given URL. */
function fetchWasCalledWith(fetchImpl: ReturnType<typeof vi.fn>, url: string) {
  return fetchImpl.mock.calls.some(([input]: [any]) => {
    const calledUrl = typeof input === "string" ? input : input.url;
    return calledUrl === url;
  });
}

describe("sw.js — cache naming and build-id versioning", () => {
  it("names the shell cache vq-shell-<buildId> after install+activate", async () => {
    const { cacheStorage } = await setupInstalledSw("build-A");
    expect(await cacheStorage.has("vq-shell-build-A")).toBe(true);
  });

  it("falls back to vq-shell-unversioned when the script URL has no ?v=", async () => {
    const { cacheStorage } = await setupInstalledSw(undefined);
    expect(await cacheStorage.has("vq-shell-unversioned")).toBe(true);
  });

  it("a deploy (new buildId) evicts the old shell cache but preserves the scripture cache", async () => {
    const cacheStorage = new FakeCacheStorage();
    const url = scriptureUrl("translations");

    const { sw: swA } = await setupInstalledSw(
      "build-A",
      { [url]: fakeNetworkResponse(JSON.stringify({ translations: ["A"] }), { status: 200 }) },
      cacheStorage,
    );
    const req = new Request(url);
    await swA.dispatchFetch(req);

    expect(await cacheStorage.has("vq-shell-build-A")).toBe(true);
    expect(await cacheStorage.has("vq-scripture-v1")).toBe(true);

    await setupInstalledSw("build-B", {}, cacheStorage);

    expect(await cacheStorage.has("vq-shell-build-A")).toBe(false);
    expect(await cacheStorage.has("vq-shell-build-B")).toBe(true);
    expect(await cacheStorage.has("vq-scripture-v1")).toBe(true);

    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await scriptureCache?.match(url)).toBeDefined();
  });

  it("a foreign, non-vq- cache survives activation untouched", async () => {
    const cacheStorage = new FakeCacheStorage();
    await cacheStorage.open("some-other-app-cache");

    await setupInstalledSw("build-A", {}, cacheStorage);

    expect(await cacheStorage.has("some-other-app-cache")).toBe(true);
  });
});

describe("sw.js — non-GET requests are structurally untouchable", () => {
  const postUrls = [
    "https://api.example.test/api/v1/chat",
    "https://api.example.test/api/v1/chat/stream",
    "https://api.example.test/api/v1/feedback",
    "https://api.example.test/api/v1/church/search",
  ];

  it.each(postUrls)("POST %s never reaches respondWith and never touches cache", async (url) => {
    const { sw, cacheStorage } = await setupInstalledSw("build-A");
    const before = await cacheStorage.keys();

    const result = await sw.dispatchFetch(new Request(url, { method: "POST" }));

    expect(result.respondWithCalled).toBe(false);
    expect(await cacheStorage.keys()).toEqual(before);
  });

  it("a pre-seeded cache entry at a chat-stream URL is never served to a POST (method check precedes lookup)", async () => {
    const url = "https://api.example.test/api/v1/chat/stream";
    const { sw, cacheStorage } = await setupInstalledSw("build-A");
    const scriptureCache = await cacheStorage.open("vq-scripture-v1");
    await scriptureCache.put(url, fakeNetworkResponse("POISON", { status: 200 }));

    const result = await sw.dispatchFetch(new Request(url, { method: "POST" }));

    expect(result.respondWithCalled).toBe(false);
    const stillThere = await scriptureCache.match(url);
    expect(await stillThere?.text()).toBe("POISON");
  });

  it("GET /api/v1/chat/verse/... is also denylisted (prefix covers GET, not just POST)", async () => {
    const url = "https://api.example.test/api/v1/chat/verse/John/3/16";
    const { sw } = await setupInstalledSw("build-A");

    const result = await sw.dispatchFetch(new Request(url));

    expect(result.respondWithCalled).toBe(false);
  });

  it("a POST to a scripture-allowlist URL is never intercepted or cached (method check runs before allowlist matching)", async () => {
    // Without the method check, this exact URL WOULD match the scripture
    // allowlist and get handled/cached — this is what actually pins the
    // "non-GET returns before any URL inspection" claim, unlike a POST to a
    // URL that no other branch would ever match anyway.
    const url = scriptureUrl("chapter/John/3");
    const { sw, cacheStorage } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse(JSON.stringify({ chapter: 3 }), { status: 200 }),
    });

    const result = await sw.dispatchFetch(new Request(url, { method: "POST", body: "{}" }));

    expect(result.respondWithCalled).toBe(false);
    expect(await cacheStorage.has("vq-scripture-v1")).toBe(false);
  });

  it("challenges.cloudflare.com is bypassed even for a path shape that would otherwise match the scripture allowlist (hostname check precedes pathname matching)", async () => {
    // Same technique as above: pick a URL that WOULD be cached by a later
    // branch if this earlier bypass were removed, so the test actually
    // exercises branch ordering instead of two branches that happen to both
    // say "don't cache" for unrelated reasons.
    const url = "https://challenges.cloudflare.com/api/v1/scripture/translations";
    const { sw, cacheStorage, fetchImpl } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse("{}", { status: 200 }),
    });

    const result = await sw.dispatchFetch(new Request(url));

    expect(result.respondWithCalled).toBe(false);
    expect(fetchWasCalledWith(fetchImpl, url)).toBe(false);
    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await scriptureCache?.match(url)).toBeUndefined();
  });

  it("the /api/v1/chat denylist check precedes the static-asset and scripture-allowlist branches in source order", () => {
    // Unlike the two tests above, no real URL can start with both
    // "/api/v1/chat" and "/api/v1/scripture/..." (disjoint prefixes), so no
    // fetch-based test can distinguish "the chat denylist runs" from "no
    // other branch matches a chat URL anyway" — this line is honest defense
    // in depth, not currently reachable-in-effect. A source-order assertion
    // is the correct tool: it fails if a future edit moves the denylist
    // after a branch it's meant to guard, which a behavioral test cannot.
    const src = readFileSync(SW_PATH, "utf8");
    const denylistIdx = src.indexOf('pathname.startsWith("/api/v1/chat")');
    const staticIdx = src.indexOf("matchesStaticAsset(url.pathname)");
    const scriptureIdx = src.indexOf("matchesScriptureAllowlist(url.pathname)");

    expect(denylistIdx).toBeGreaterThan(-1);
    expect(staticIdx).toBeGreaterThan(-1);
    expect(scriptureIdx).toBeGreaterThan(-1);
    expect(denylistIdx).toBeLessThan(staticIdx);
    expect(denylistIdx).toBeLessThan(scriptureIdx);
  });

  it("never calls self.skipWaiting() outside of the design-decision comment (design decision A2)", () => {
    const src = readFileSync(SW_PATH, "utf8");
    const withoutComments = src
      .replace(/\/\*\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");
    expect(withoutComments).not.toMatch(/skipWaiting\s*\(/);
  });
});

describe("sw.js — Turnstile token safety", () => {
  it("a scripture GET carrying X-Turnstile-Token gets cached, keyed by bare URL string with no header retained", async () => {
    const url = scriptureUrl("verse/John/3/16");
    const { sw, cacheStorage } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse(JSON.stringify({ verse: 16 }), { status: 200 }),
    });

    const request = new Request(url, {
      headers: { "X-Turnstile-Token": "tok-123" },
    });
    const result = await sw.dispatchFetch(request);
    expect(result.respondWithCalled).toBe(true);

    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    const keys = await scriptureCache?.keys();
    expect(keys).toEqual([{ url }]); // plain string key — no headers, no way to leak the token
    expect(await scriptureCache?.match(url)).toBeDefined();
    // The `keys()` shape above is identical whether sw.js wrote `request.url`
    // (a string) or `request` (a Request object) — FakeCache.keyFor() collapses
    // both to the same map key. `keyType()` tracks what was actually passed to
    // `cache.put`, which is what pins the real Cache API's behavior: a stored
    // `Request` object retains its headers (including X-Turnstile-Token) in a
    // real browser's CacheStorage; a bare string does not.
    expect(scriptureCache?.keyType(url)).toBe("string");
  });

  it("a response with Vary: X-Turnstile-Token is never cached", async () => {
    const url = scriptureUrl("translations");
    const { sw, cacheStorage } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse(JSON.stringify({ translations: [] }), {
        status: 200,
        headers: { Vary: "X-Turnstile-Token" },
      }),
    });

    await sw.dispatchFetch(new Request(url));

    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await scriptureCache?.match(url)).toBeUndefined();
  });

  it("a response echoing X-Turnstile-Token back is never cached", async () => {
    const url = scriptureUrl("translations");
    const { sw, cacheStorage } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse(JSON.stringify({ translations: [] }), {
        status: 200,
        headers: { "X-Turnstile-Token": "tok-echoed" },
      }),
    });

    await sw.dispatchFetch(new Request(url));

    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await scriptureCache?.match(url)).toBeUndefined();
  });
});

describe("sw.js — Turnstile widget origin passthrough", () => {
  it("never intercepts challenges.cloudflare.com", async () => {
    const { sw, fetchImpl } = await setupInstalledSw("build-A");
    const url = "https://challenges.cloudflare.com/turnstile/v0/api.js";

    const result = await sw.dispatchFetch(new Request(url));

    expect(result.respondWithCalled).toBe(false);
    expect(fetchWasCalledWith(fetchImpl, url)).toBe(false);
  });
});

describe("sw.js — scripture stale-while-revalidate", () => {
  it("cold GET: fetches from network once and caches the result", async () => {
    const url = scriptureUrl("book-names");
    const { sw, cacheStorage, fetchImpl } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse(JSON.stringify({ v: 1 }), { status: 200 }),
    });

    const result = await sw.dispatchFetch(new Request(url));

    expect(await result.response?.json()).toEqual({ v: 1 });
    expect(fetchImpl).toHaveBeenCalledTimes(2); // offline.html precache (install) + this
    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await (await scriptureCache?.match(url))?.json()).toEqual({ v: 1 });
  });

  it("warm GET: serves stale content immediately, then updates the cache in the background", async () => {
    const url = scriptureUrl("chapter/John/3");
    const { sw, cacheStorage, fetchImpl } = await setupInstalledSw("build-A", {
      [url]: [
        fakeNetworkResponse(JSON.stringify({ v: 1 }), { status: 200 }),
        fakeNetworkResponse(JSON.stringify({ v: 2 }), { status: 200 }),
      ],
    });

    const first = await sw.dispatchFetch(new Request(url));
    expect(await first.response?.json()).toEqual({ v: 1 });

    const second = await sw.dispatchFetch(new Request(url));
    expect(await second.response?.json()).toEqual({ v: 1 }); // stale, served immediately
    expect(fetchImpl).toHaveBeenCalledTimes(3); // offline.html + 2 scripture calls

    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await (await scriptureCache?.match(url))?.json()).toEqual({ v: 2 }); // revalidated
  });

  it("warm GET + network rejects: still serves the cached content without throwing", async () => {
    const url = scriptureUrl("translations");
    const { sw, cacheStorage } = await setupInstalledSw("build-A", {
      [url]: [
        fakeNetworkResponse(JSON.stringify({ v: 1 }), { status: 200 }),
        new Error("network down"),
      ],
    });

    await sw.dispatchFetch(new Request(url));
    const second = await sw.dispatchFetch(new Request(url));

    expect(await second.response?.json()).toEqual({ v: 1 });
    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await (await scriptureCache?.match(url))?.json()).toEqual({ v: 1 }); // unchanged
  });

  it("cold GET + network rejects: does not throw and caches nothing", async () => {
    const url = scriptureUrl("verse/John/3/16");
    const { sw, cacheStorage } = await setupInstalledSw("build-A", {
      [url]: new Error("network down"),
    });

    const result = await sw.dispatchFetch(new Request(url));

    expect(result.response).toBeDefined();
    expect(result.response?.status).toBe(0); // Response.error()
    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await scriptureCache?.match(url)).toBeUndefined();
  });

  it("caches translations, book-names, and verse/ GETs but never search", async () => {
    const translationsUrl = scriptureUrl("translations");
    const bookNamesUrl = scriptureUrl("book-names");
    const verseUrl = scriptureUrl("verse/John/3/16");
    const searchUrl = scriptureUrl("search?q=love");

    const { sw, cacheStorage, fetchImpl } = await setupInstalledSw("build-A", {
      [translationsUrl]: fakeNetworkResponse("{}", { status: 200 }),
      [bookNamesUrl]: fakeNetworkResponse("{}", { status: 200 }),
      [verseUrl]: fakeNetworkResponse("{}", { status: 200 }),
    });

    await sw.dispatchFetch(new Request(translationsUrl));
    await sw.dispatchFetch(new Request(bookNamesUrl));
    await sw.dispatchFetch(new Request(verseUrl));
    const searchResult = await sw.dispatchFetch(new Request(searchUrl));

    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await scriptureCache?.match(translationsUrl)).toBeDefined();
    expect(await scriptureCache?.match(bookNamesUrl)).toBeDefined();
    expect(await scriptureCache?.match(verseUrl)).toBeDefined();

    expect(searchResult.respondWithCalled).toBe(false);
    expect(await scriptureCache?.match(searchUrl)).toBeUndefined();
    expect(fetchWasCalledWith(fetchImpl, searchUrl)).toBe(false);
  });

  it("a 500 scripture response is returned but never cached", async () => {
    const url = scriptureUrl("translations");
    const { sw, cacheStorage } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse("", { status: 500 }),
    });

    const result = await sw.dispatchFetch(new Request(url));

    expect(result.response?.status).toBe(500);
    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    expect(await scriptureCache?.match(url)).toBeUndefined();
  });

  it("trims the scripture cache to SCRIPTURE_CACHE_MAX_ENTRIES, evicting oldest first", async () => {
    const total = 105;
    const max = 100;
    const routes: Record<string, Route> = {};
    for (let i = 1; i <= total; i++) {
      routes[scriptureUrl(`verse/John/3/${i}`)] = fakeNetworkResponse("{}", { status: 200 });
    }
    const { sw, cacheStorage } = await setupInstalledSw("build-A", routes);

    for (let i = 1; i <= total; i++) {
      await sw.dispatchFetch(new Request(scriptureUrl(`verse/John/3/${i}`)));
    }

    const scriptureCache = cacheStorage.__get("vq-scripture-v1");
    const keys = await scriptureCache?.keys();
    expect(keys).toHaveLength(max);

    // Oldest (i=1..5) evicted, newest (i=6..105) retained.
    for (let i = 1; i <= total - max; i++) {
      expect(await scriptureCache?.match(scriptureUrl(`verse/John/3/${i}`))).toBeUndefined();
    }
    for (let i = total - max + 1; i <= total; i++) {
      expect(await scriptureCache?.match(scriptureUrl(`verse/John/3/${i}`))).toBeDefined();
    }
  });
});

describe("sw.js — offline navigation fallback", () => {
  it("precaches /offline.html into the shell cache on install", async () => {
    const { cacheStorage } = await setupInstalledSw("build-A");
    const shellCache = cacheStorage.__get("vq-shell-build-A");
    const cached = await shellCache?.match("/offline.html");
    expect(await cached?.text()).toBe(OFFLINE_HTML);
  });

  it("serves the precached offline page when a navigation request's network fetch rejects", async () => {
    const navUrl = "https://example.test/en";
    const { sw } = await setupInstalledSw("build-A", {
      [navUrl]: new Error("offline"),
    });

    const navigationRequest = { url: navUrl, method: "GET", mode: "navigate" } as unknown as Request;
    const result = await sw.dispatchFetch(navigationRequest);

    expect(result.respondWithCalled).toBe(true);
    expect(await result.response?.text()).toBe(OFFLINE_HTML);
  });

  it("returns the network response for a successful navigation and caches nothing", async () => {
    const navUrl = "https://example.test/en";
    const { sw, cacheStorage } = await setupInstalledSw("build-A", {
      [navUrl]: fakeNetworkResponse("<html>PAGE</html>", {
        status: 200,
        headers: { "Content-Type": "text/html" },
      }),
    });

    const navigationRequest = { url: navUrl, method: "GET", mode: "navigate" } as unknown as Request;
    const result = await sw.dispatchFetch(navigationRequest);

    expect(await result.response?.text()).toBe("<html>PAGE</html>");
    const shellCache = cacheStorage.__get("vq-shell-build-A");
    expect(await shellCache?.match(navUrl)).toBeUndefined();
    const keys = await shellCache?.keys();
    expect(keys).toEqual([{ url: "/offline.html" }]); // nothing else was ever written
  });
});

describe("sw.js — passthrough and static-asset caching", () => {
  it("never answers /manifest.webmanifest from cache or the offline page", async () => {
    const { sw } = await setupInstalledSw("build-A");
    const result = await sw.dispatchFetch(
      new Request("https://example.test/manifest.webmanifest"),
    );
    expect(result.respondWithCalled).toBe(false);
  });

  it("serves an icon cache-first, not the offline page", async () => {
    const url = "https://example.test/icons/icon-192.png";
    const { sw } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse("PNGDATA", { status: 200 }),
    });

    const result = await sw.dispatchFetch(new Request(url));

    const body = await result.response?.text();
    expect(body).toBe("PNGDATA");
    expect(body).not.toBe(OFFLINE_HTML);
  });

  it("caches a _next/static asset and serves the second identical request from cache (network hit once)", async () => {
    const url = "https://example.test/_next/static/chunks/main-abc.js";
    const { sw, fetchImpl } = await setupInstalledSw("build-A", {
      [url]: fakeNetworkResponse("JSDATA", { status: 200 }),
    });

    const first = await sw.dispatchFetch(new Request(url));
    expect(await first.response?.text()).toBe("JSDATA");

    const second = await sw.dispatchFetch(new Request(url));
    expect(await second.response?.text()).toBe("JSDATA");

    // Only the offline.html precache (install) + one network fetch for this asset.
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });
});
