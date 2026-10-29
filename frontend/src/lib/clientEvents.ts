/**
 * BITB-119 / BITB-247: tiny, privacy-preserving client telemetry for the read-aloud feature.
 *
 * Posts ONLY `{event, locale, platform, browser, os}` to the backend sink
 * (POST /api/v1/client-events), which increments an OTel counter and a daily
 * aggregate. `browser` and `os` are coarse families from fixed lists, computed
 * here from `navigator.userAgentData` or the user-agent string; the raw user
 * agent is never sent. No message text, ids or user data either.
 * Fire-and-forget: it must never throw or block the UI (mirrors clientErrorReporter.ts).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ClientEventName =
  | "tts_started"
  | "tts_completed"
  | "tts_start_failed"
  | "tts_error"
  | "tts_unavailable";

export type BrowserFamily =
  "chrome" | "firefox" | "safari" | "edge" | "samsung" | "other";

export type OsFamily =
  "android" | "ios" | "linux" | "windows" | "macos" | "other";

/** The subset of `navigator` the detectors read (injectable for tests). */
export interface NavigatorLike {
  userAgent?: string;
  maxTouchPoints?: number;
  userAgentData?: {
    brands?: { brand: string; version?: string }[];
    platform?: string;
  };
}

function currentNavigator(): NavigatorLike {
  if (typeof navigator === "undefined") return {};
  return navigator as unknown as NavigatorLike;
}

/** Browser family from `userAgentData` brands when present, else the UA string. */
export function detectBrowserFamily(
  nav: NavigatorLike = currentNavigator(),
): BrowserFamily {
  const brands = (nav.userAgentData?.brands ?? []).map((b) =>
    (b.brand ?? "").toLowerCase(),
  );
  if (brands.length > 0) {
    // Chromium-based browsers list "Chromium" too, so check the specific ones first.
    if (brands.some((b) => b.includes("edge"))) return "edge";
    if (brands.some((b) => b.includes("samsung"))) return "samsung";
    if (brands.some((b) => b.includes("opera"))) return "other";
    if (brands.some((b) => b.includes("google chrome") || b === "chromium")) {
      return "chrome";
    }
  }
  const ua = nav.userAgent ?? "";
  if (/SamsungBrowser/i.test(ua)) return "samsung";
  if (/Edg(e|A|iOS)?\//.test(ua)) return "edge";
  if (/OPR\/|OPiOS|Opera/i.test(ua)) return "other";
  if (/FxiOS|Firefox/i.test(ua)) return "firefox";
  if (/CriOS|Chrome|Chromium/i.test(ua)) return "chrome";
  if (/Safari/i.test(ua)) return "safari";
  return "other";
}

/** OS family from `userAgentData.platform` when present, else the UA string. */
export function detectOsFamily(
  nav: NavigatorLike = currentNavigator(),
): OsFamily {
  const platform = (nav.userAgentData?.platform ?? "").toLowerCase();
  if (platform) {
    if (platform === "android") return "android";
    if (platform === "ios") return "ios";
    if (platform === "windows") return "windows";
    if (platform === "macos") return "macos";
    if (platform === "linux") return "linux";
    // "Chrome OS", "Unknown", ...: fall through to the UA string, then "other".
  }
  const ua = nav.userAgent ?? "";
  // iOS first: its UA also says "like Mac OS X".
  if (/iPhone|iPad|iPod/i.test(ua)) return "ios";
  // iPadOS 13+ asks for the desktop site: a "Macintosh" UA on a touch device.
  if (/Macintosh/.test(ua) && (nav.maxTouchPoints ?? 0) > 1) return "ios";
  // Android before Linux: Android UAs also say "Linux".
  if (/Android/i.test(ua)) return "android";
  if (/Windows/i.test(ua)) return "windows";
  if (/Macintosh|Mac OS X/i.test(ua)) return "macos";
  if (/CrOS/.test(ua)) return "other";
  if (/Linux|X11/i.test(ua)) return "linux";
  return "other";
}

const unavailableReported = new Set<string>();

/** Test-only: forget which events were already reported. */
export function __resetClientEventsForTest(): void {
  unavailableReported.clear();
}

export function reportClientEvent(
  event: ClientEventName,
  locale: string,
): void {
  if (typeof window === "undefined") return;
  try {
    const nav = currentNavigator();
    void fetch(`${API_URL}/api/v1/client-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event,
        locale,
        platform: "web",
        browser: detectBrowserFamily(nav),
        os: detectOsFamily(nav),
      }),
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
