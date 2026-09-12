/**
 * Registers the versioned offline-shell service worker (BITB-102).
 *
 * `public/build-info.json` (written at build time by
 * `scripts/generate-build-info.mjs`) is the single source of truth for the
 * current build id — this reads it via `fetch`, never `process.env`
 * directly, so the same logic works regardless of how/when this module is
 * evaluated. The id is appended as `?v=<buildId>` on the service worker's
 * script URL: `public/sw.js` reads it back off `self.location` to name its
 * shell cache, so a new deploy (new buildId) evicts the old shell cache
 * instead of leaving an installed user pinned to a stale one forever.
 *
 * Production-only: in any other environment (`npm run dev`, tests, a
 * preview build served with NODE_ENV !== "production") this actively
 * *unregisters* any existing service worker instead of registering one, so
 * HMR isn't fought by a stale worker and a developer who once ran a
 * production build locally isn't wedged with a worker they can't get rid of.
 *
 * Fails closed and never throws: any error here must not break the page.
 */

import { reportClientError } from "@/lib/clientErrorReporter";

interface RegisterServiceWorkerOptions {
  isProduction?: boolean;
}

interface BuildInfo {
  buildId?: string;
}

export async function registerServiceWorker(
  opts?: RegisterServiceWorkerOptions,
): Promise<ServiceWorkerRegistration | null> {
  try {
    if (
      typeof navigator === "undefined" ||
      !("serviceWorker" in navigator)
    ) {
      return null;
    }

    if (typeof window === "undefined" || !window.isSecureContext) {
      return null;
    }

    const isProduction =
      opts?.isProduction ?? process.env.NODE_ENV === "production";

    if (!isProduction) {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((r) => r.unregister()));
      return null;
    }

    let buildId: string | undefined;
    try {
      const response = await fetch("/build-info.json", { cache: "no-store" });
      if (!response.ok) return null;
      const data: BuildInfo = await response.json();
      buildId = data?.buildId?.trim();
    } catch {
      // Network error, malformed JSON, etc. — fail closed: registering with
      // no build id would create a shell cache that never invalidates.
      return null;
    }

    if (!buildId) return null;

    return await navigator.serviceWorker.register(
      `/sw.js?v=${encodeURIComponent(buildId)}`,
      { scope: "/", updateViaCache: "none" },
    );
  } catch (error) {
    reportClientError(
      "api_failure",
      error instanceof Error
        ? `sw_register: ${error.stack || error.message}`
        : `sw_register: ${String(error)}`,
    );
    return null;
  }
}
