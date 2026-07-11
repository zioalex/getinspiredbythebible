/**
 * Smoke-test bypass reader (BITB-064).
 *
 * The production browser smoke test needs to get past Cloudflare Turnstile
 * deterministically (a headless CI browser can't reliably solve an invisible
 * challenge). Rather than bake a bypass secret into the shipped bundle — which
 * would hand every real user a Turnstile + rate-limit bypass — the deployed
 * bundle only READS a value that the Playwright test injects at runtime via
 * `addInitScript` (so it exists solely in the ephemeral CI browser session):
 *
 *     window.__VOXQUIETA_SMOKE_SECRET__ = "<secret>";
 *
 * When present, api.ts attaches it as the X-Monitor-Probe-Secret header and the
 * chat UI relaxes the send gate. For real users the global is `undefined`, so
 * this is entirely inert. The value is NEVER a NEXT_PUBLIC_* env var and is
 * never shipped in the bundle.
 */

declare global {
  interface Window {
    __VOXQUIETA_SMOKE_SECRET__?: unknown;
  }
}

/** The injected smoke secret, or null (real users, SSR). */
export function getSmokeSecret(): string | null {
  if (typeof window === "undefined") return null;
  const value = window.__VOXQUIETA_SMOKE_SECRET__;
  return typeof value === "string" && value.length > 0 ? value : null;
}

/** Whether the current browser session is a smoke test. */
export function isSmokeMode(): boolean {
  return getSmokeSecret() !== null;
}
