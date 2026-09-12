/**
 * Test harness for BITB-102's public/sw.js.
 *
 * Loads and executes the ACTUAL SHIPPED service worker file (not a
 * reimplementation) inside the Vitest/Node process via `new Function(...)`,
 * fed a faked `self`/`CacheStorage`/`fetch` so its `install`/`activate`/
 * `fetch` handlers can be driven and asserted on directly.
 *
 * `src/test/**` is excluded from `tsconfig.json`'s type-checking (see
 * tsconfig.json `exclude`), so this file intentionally stays loose with
 * types (`any` throughout) rather than fighting the DOM lib types for a
 * service-worker-shaped fake environment.
 */

import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SW_PATH = resolve(__dirname, "../../public/sw.js");

function keyFor(requestOrUrl: any): string {
  return typeof requestOrUrl === "string" ? requestOrUrl : requestOrUrl.url;
}

/** A single named cache, backed by a Map that preserves insertion order (for FIFO trim tests). */
class FakeCache {
  private store = new Map<string, Response>();
  private getFetchImpl: () => (input: any) => Promise<Response>;

  constructor(getFetchImpl: () => (input: any) => Promise<Response>) {
    this.getFetchImpl = getFetchImpl;
  }

  async match(requestOrUrl: any): Promise<Response | undefined> {
    const res = this.store.get(keyFor(requestOrUrl));
    return res ? res.clone() : undefined;
  }

  async put(requestOrUrl: any, response: Response): Promise<void> {
    this.store.set(keyFor(requestOrUrl), response);
  }

  async delete(requestOrUrl: any): Promise<boolean> {
    return this.store.delete(keyFor(requestOrUrl));
  }

  /** Returns Request-like objects (just `{url}`) preserving insertion order. */
  async keys(): Promise<{ url: string }[]> {
    return [...this.store.keys()].map((url) => ({ url }));
  }

  async addAll(requests: any[]): Promise<void> {
    const fetchImpl = this.getFetchImpl();
    for (const req of requests) {
      const response = await fetchImpl(req);
      if (!response || !response.ok) {
        throw new Error(`FakeCache.addAll: failed to fetch ${keyFor(req)}`);
      }
      this.store.set(keyFor(req), response);
    }
  }

  /** Test-only inspection helper — not part of the real Cache API. */
  __size(): number {
    return this.store.size;
  }
}

/**
 * A fake CacheStorage, constructible standalone and shareable across two
 * separate `loadServiceWorker()` calls (needed for the deploy-invalidation
 * test, which loads two SW "versions" against one shared storage).
 */
export class FakeCacheStorage {
  private caches = new Map<string, FakeCache>();
  /** Set by loadServiceWorker before each install so cache.addAll() can reach that SW's fetch. */
  fetchImpl: (input: any) => Promise<Response> = () => {
    throw new Error("FakeCacheStorage.fetchImpl not configured");
  };

  async open(name: string): Promise<FakeCache> {
    let cache = this.caches.get(name);
    if (!cache) {
      cache = new FakeCache(() => this.fetchImpl);
      this.caches.set(name, cache);
    }
    return cache;
  }

  async keys(): Promise<string[]> {
    return [...this.caches.keys()];
  }

  async delete(name: string): Promise<boolean> {
    return this.caches.delete(name);
  }

  async has(name: string): Promise<boolean> {
    return this.caches.has(name);
  }

  /** Test-only: read a cache without going through the public `open` semantics. */
  __get(name: string): FakeCache | undefined {
    return this.caches.get(name);
  }
}

/**
 * Build a Response that looks like a real network response for `isCacheableResponse`'s
 * purposes. A `Response` built via `new Response(...)` always reports `type: "default"`
 * — real "basic"/"cors"/"opaque" types are only assigned by the browser's network stack
 * for an actual fetch. Since `type` is a configurable accessor on the prototype, we stamp
 * an own-property override so fake fetch responses behave like real ones for the
 * sw.js code under test (which gates caching on `type === "basic" || type === "cors"`).
 */
export function fakeNetworkResponse(
  body: BodyInit | null,
  init: ResponseInit = {},
  type: "basic" | "cors" | "opaque" = "basic",
): Response {
  const response = new Response(body, init);
  Object.defineProperty(response, "type", { value: type, configurable: true });
  return response;
}

function makeFakeEvent() {
  const waitUntilPromises: Promise<unknown>[] = [];
  let respondWithPromise: Promise<unknown> | undefined;
  let respondWithCalled = false;

  return {
    waitUntil(p: unknown) {
      waitUntilPromises.push(Promise.resolve(p));
    },
    respondWith(p: unknown) {
      respondWithCalled = true;
      respondWithPromise = Promise.resolve(p);
    },
    get _waitUntilPromises() {
      return waitUntilPromises;
    },
    get _respondWithPromise() {
      return respondWithPromise;
    },
    get _respondWithCalled() {
      return respondWithCalled;
    },
  };
}

export interface LoadServiceWorkerOptions {
  buildId?: string | null;
  cacheStorage: FakeCacheStorage;
  fetchImpl: (input: any) => Promise<Response>;
}

export function loadServiceWorker({
  buildId,
  cacheStorage,
  fetchImpl,
}: LoadServiceWorkerOptions) {
  const src = readFileSync(SW_PATH, "utf8");

  const href =
    buildId === undefined || buildId === null
      ? "https://example.test/sw.js"
      : `https://example.test/sw.js?v=${encodeURIComponent(buildId)}`;

  const handlers: Record<string, (event: any) => unknown> = {};

  const fakeSelf: any = {
    location: new URL(href),
    addEventListener(type: string, fn: (event: any) => unknown) {
      handlers[type] = fn;
    },
    clients: {
      claim: () => Promise.resolve(),
    },
    skipWaiting: () => Promise.resolve(),
    registration: {},
  };

  // Route this SW instance's cache.addAll() calls through its own fetchImpl.
  cacheStorage.fetchImpl = fetchImpl;

  const run = new Function(
    "self",
    "caches",
    "fetch",
    "Response",
    "Request",
    "Headers",
    "URL",
    "console",
    src,
  );
  run(fakeSelf, cacheStorage, fetchImpl, Response, Request, Headers, URL, console);

  async function dispatch(type: "install" | "activate") {
    const handler = handlers[type];
    if (!handler) throw new Error(`sw.js registered no "${type}" handler`);
    const event = makeFakeEvent();
    handler(event);
    await Promise.all(event._waitUntilPromises);
    return { waitUntilPromises: event._waitUntilPromises };
  }

  return {
    buildId,
    self: fakeSelf,
    async dispatchInstall() {
      return dispatch("install");
    },
    async dispatchActivate() {
      return dispatch("activate");
    },
    async dispatchFetch(request: Request) {
      const handler = handlers.fetch;
      if (!handler) throw new Error('sw.js registered no "fetch" handler');
      const event = makeFakeEvent();
      (event as any).request = request;
      handler(event);

      let response: Response | undefined;
      if (event._respondWithPromise) {
        response = (await event._respondWithPromise) as Response;
      }
      await Promise.all(event._waitUntilPromises);

      return {
        response,
        respondWithCalled: event._respondWithCalled,
        waitUntilPromises: event._waitUntilPromises,
      };
    },
  };
}
