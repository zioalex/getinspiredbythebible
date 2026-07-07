/**
 * Client-side error reporter (BITB-066).
 *
 * Sends JS errors, unhandled promise rejections, React render errors, and API
 * failures to the backend POST /api/v1/client-errors sink, which records the
 * client.errors_total metric so a spike (e.g. a browser-only outage) alerts.
 *
 * Design constraints:
 *  - Fire-and-forget: it must NEVER throw, or it would re-enter the
 *    unhandledrejection handler and loop.
 *  - PII-scrubbing + length-capped detail (mirrors the backend cap).
 *  - Per-session cap + dedupe so a repeating error can't flood the endpoint.
 *  - SSR-safe: every window access is guarded.
 *
 * Mirrors the existing reportTurnstileError pattern in lib/turnstile.tsx.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Bounded set of report types — matches the backend metric `type` whitelist. */
export type ClientErrorType =
  | "window_onerror"
  | "unhandledrejection"
  | "api_failure"
  | "react_render";

/** Max reports per page load — a repeating error can't flood the endpoint. */
export const MAX_REPORTS_PER_SESSION = 10;
/** Detail length cap (mirrors settings.client_error_max_detail_chars). */
export const MAX_DETAIL_CHARS = 500;

let reportCount = 0;
const seenKeys = new Set<string>();

/** Test-only: reset the per-session cap/dedupe state. */
export function __resetReporterStateForTest(): void {
  reportCount = 0;
  seenKeys.clear();
}

/**
 * Remove obvious PII / secrets from a free-text error detail and cap its length.
 * Pure function — unit-testable without a DOM or fetch.
 */
export function scrubPII(detail: string): string {
  if (!detail) return "";
  const scrubbed = detail
    // emails
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, "[email]")
    // JWTs / bearer / API-key-like long tokens
    .replace(
      /\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g,
      "[jwt]",
    )
    .replace(/\b[A-Za-z0-9_-]{24,}\b/g, "[token]")
    // long digit runs (phone numbers, ids)
    .replace(/\b\d{7,}\b/g, "[num]");
  return scrubbed.length > MAX_DETAIL_CHARS
    ? scrubbed.slice(0, MAX_DETAIL_CHARS)
    : scrubbed;
}

/**
 * Whether this (type, detail) should be reported: enforces the per-session cap
 * and dedupes identical reports. Pure aside from module-level counters.
 */
export function shouldReport(type: ClientErrorType, detail: string): boolean {
  if (reportCount >= MAX_REPORTS_PER_SESSION) return false;
  const key = `${type}:${detail}`;
  if (seenKeys.has(key)) return false;
  seenKeys.add(key);
  reportCount += 1;
  return true;
}

/**
 * Report a client-side error. Fire-and-forget; never throws.
 */
export function reportClientError(
  type: ClientErrorType,
  rawDetail: string,
): void {
  if (typeof window === "undefined") return;
  try {
    const detail = scrubPII(rawDetail);
    if (!shouldReport(type, detail)) return;
    // fire-and-forget; swallow all errors so we never re-enter our own handler
    void fetch(`${API_URL}/api/v1/client-errors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, detail }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // never throw from the reporter
  }
}
