/**
 * BITB-119: tiny, privacy-preserving client telemetry for the read-aloud feature.
 *
 * Posts ONLY `{event, locale}` to the backend sink (POST /api/v1/client-events), which
 * increments an OTel counter. No message text, ids or user data are ever sent.
 * Fire-and-forget: it must never throw or block the UI (mirrors clientErrorReporter.ts).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ClientEventName = "tts_started" | "tts_unavailable";

const unavailableReported = new Set<string>();

/** Test-only: forget which locales were already reported as unavailable. */
export function __resetClientEventsForTest(): void {
  unavailableReported.clear();
}

export function reportClientEvent(
  event: ClientEventName,
  locale: string,
): void {
  if (typeof window === "undefined") return;
  try {
    void fetch(`${API_URL}/api/v1/client-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, locale }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // never throw from telemetry
  }
}

/** `tts_unavailable` is reported at most once per locale per page load. */
export function reportTtsUnavailableOnce(locale: string): void {
  if (unavailableReported.has(locale)) return;
  unavailableReported.add(locale);
  reportClientEvent("tts_unavailable", locale);
}
