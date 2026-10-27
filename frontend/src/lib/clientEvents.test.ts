import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  __resetClientEventsForTest,
  detectBrowserFamily,
  detectOsFamily,
  reportClientEvent,
  reportTtsEvent,
  reportTtsUnavailableOnce,
  type ClientEventName,
} from "./clientEvents";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  __resetClientEventsForTest();
  fetchMock = vi.fn(() => Promise.resolve({ ok: true } as Response));
  global.fetch = fetchMock as unknown as typeof fetch;
});

const UA = {
  chromeWin:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
  chromeMac:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
  chromeAndroid:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
  chromeIos:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.6478.153 Mobile/15E148 Safari/604.1",
  firefoxWin:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
  firefoxLinux:
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
  firefoxAndroid:
    "Mozilla/5.0 (Android 14; Mobile; rv:127.0) Gecko/127.0 Firefox/127.0",
  firefoxIos:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/127.0 Mobile/15E148 Safari/605.1.15",
  safariMac:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
  safariIos:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  safariIpadDesktop:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
  edgeWin:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
  edgeAndroid:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 EdgA/126.0.0.0",
  edgeIos:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 EdgiOS/126.0.0.0 Mobile/15E148 Safari/605.1.15",
  samsungAndroid:
    "Mozilla/5.0 (Linux; Android 14; SAMSUNG SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Mobile Safari/537.36",
  samsungDesktop:
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Safari/537.36",
  operaWin:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/111.0.0.0",
};

describe("detectBrowserFamily / detectOsFamily (user-agent string)", () => {
  it.each([
    ["chromeWin", "chrome", "windows"],
    ["chromeMac", "chrome", "macos"],
    ["chromeAndroid", "chrome", "android"],
    ["chromeIos", "chrome", "ios"],
    ["firefoxWin", "firefox", "windows"],
    ["firefoxLinux", "firefox", "linux"],
    ["firefoxAndroid", "firefox", "android"],
    ["firefoxIos", "firefox", "ios"],
    ["safariMac", "safari", "macos"],
    ["safariIos", "safari", "ios"],
    ["edgeWin", "edge", "windows"],
    ["edgeAndroid", "edge", "android"],
    ["edgeIos", "edge", "ios"],
    ["samsungAndroid", "samsung", "android"],
    ["samsungDesktop", "samsung", "linux"],
    ["operaWin", "other", "windows"],
  ] as const)("%s -> %s / %s", (key, browser, os) => {
    expect(detectBrowserFamily({ userAgent: UA[key] })).toBe(browser);
    expect(detectOsFamily({ userAgent: UA[key] })).toBe(os);
  });

  it("treats a touch-screen desktop-class Safari as iPadOS", () => {
    const nav = { userAgent: UA.safariIpadDesktop, maxTouchPoints: 5 };
    expect(detectBrowserFamily(nav)).toBe("safari");
    expect(detectOsFamily(nav)).toBe("ios");
    expect(detectOsFamily({ userAgent: UA.safariIpadDesktop })).toBe("macos");
  });

  it("returns other for empty or unknown input, never the raw string", () => {
    expect(detectBrowserFamily({})).toBe("other");
    expect(detectOsFamily({})).toBe("other");
    expect(detectBrowserFamily({ userAgent: "curl/8.0" })).toBe("other");
    expect(detectOsFamily({ userAgent: "curl/8.0" })).toBe("other");
    expect(
      detectOsFamily({ userAgent: "Mozilla/5.0 (X11; CrOS x86_64)" }),
    ).toBe("other");
  });
});

describe("detectBrowserFamily / detectOsFamily (userAgentData)", () => {
  const brands = (...names: string[]) =>
    names.map((brand) => ({ brand, version: "126" }));

  it.each([
    [brands("Not/A)Brand", "Chromium", "Google Chrome"), "chrome"],
    [brands("Not/A)Brand", "Chromium", "Microsoft Edge"), "edge"],
    [brands("Not/A)Brand", "Chromium", "Samsung Internet"), "samsung"],
    [brands("Not/A)Brand", "Chromium", "Opera"), "other"],
    [brands("Not/A)Brand", "Chromium", "Brave"), "chrome"],
  ] as const)("brands %j -> %s", (b, expected) => {
    // A deliberately misleading UA proves the brands win when present.
    const nav = {
      userAgent: "Mozilla/5.0 Firefox/127.0",
      userAgentData: { brands: [...b], platform: "Windows" },
    };
    expect(detectBrowserFamily(nav)).toBe(expected);
  });

  it.each([
    ["Android", "android"],
    ["iOS", "ios"],
    ["Windows", "windows"],
    ["macOS", "macos"],
    ["Linux", "linux"],
  ] as const)("platform %s -> %s", (platform, expected) => {
    expect(detectOsFamily({ userAgent: "", userAgentData: { platform } })).toBe(
      expected,
    );
  });

  it("falls back to the UA string when brands/platform are unusable", () => {
    const nav = {
      userAgent: UA.firefoxLinux,
      userAgentData: { brands: [], platform: "Chrome OS" },
    };
    expect(detectBrowserFamily(nav)).toBe("firefox");
    expect(detectOsFamily(nav)).toBe("linux");
  });
});

describe("reportClientEvent", () => {
  function stubNavigator(userAgent: string) {
    vi.stubGlobal("navigator", { userAgent, maxTouchPoints: 0 });
  }

  afterEach(() => {
    vi.unstubAllGlobals();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it("posts only {event, locale, platform, browser, os} to the sink", () => {
    stubNavigator(UA.firefoxIos);
    reportClientEvent("tts_started", "ko");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/client-events$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      event: "tts_started",
      locale: "ko",
      platform: "web",
      browser: "firefox",
      os: "ios",
    });
    expect(Object.keys(JSON.parse(init.body)).sort()).toEqual([
      "browser",
      "event",
      "locale",
      "os",
      "platform",
    ]);
    // The raw user agent must never be in the request.
    expect(String(init.body)).not.toContain("Mozilla");
  });

  it.each([
    "tts_started",
    "tts_completed",
    "tts_start_failed",
    "tts_error",
    "tts_unavailable",
  ] as ClientEventName[])("accepts the %s event", (event) => {
    stubNavigator(UA.chromeAndroid);
    reportClientEvent(event, "de");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      event,
      locale: "de",
      platform: "web",
      browser: "chrome",
      os: "android",
    });
  });

  it("never throws when fetch rejects or throws synchronously", () => {
    fetchMock.mockReturnValueOnce(Promise.reject(new Error("offline")));
    expect(() => reportClientEvent("tts_started", "en")).not.toThrow();
    fetchMock.mockImplementationOnce(() => {
      throw new Error("boom");
    });
    expect(() => reportClientEvent("tts_started", "en")).not.toThrow();
  });
});

describe("reportTtsUnavailableOnce", () => {
  it("reports at most once per locale", () => {
    reportTtsUnavailableOnce("hi");
    reportTtsUnavailableOnce("hi");
    reportTtsUnavailableOnce("ar");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const bodies = fetchMock.mock.calls.map((c) => JSON.parse(c[1].body));
    expect(bodies).toMatchObject([
      { event: "tts_unavailable", locale: "hi", platform: "web" },
      { event: "tts_unavailable", locale: "ar", platform: "web" },
    ]);
  });
});

describe("reportTtsEvent", () => {
  it("sends at most once per (answer, event)", () => {
    expect(reportTtsEvent("tts_started", "en", "a1")).toBe(true);
    expect(reportTtsEvent("tts_started", "en", "a1")).toBe(false);
    expect(reportTtsEvent("tts_completed", "en", "a1")).toBe(true);
    expect(reportTtsEvent("tts_started", "en", "a2")).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not dedupe when no answer id is given", () => {
    reportTtsEvent("tts_error", "en");
    reportTtsEvent("tts_error", "en");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("keeps its dedupe memory bounded", () => {
    for (let i = 0; i < 600; i++) reportTtsEvent("tts_started", "en", `a${i}`);
    fetchMock.mockClear();
    // The oldest key was evicted, so it can be sent again; a recent one cannot.
    expect(reportTtsEvent("tts_started", "en", "a0")).toBe(true);
    expect(reportTtsEvent("tts_started", "en", "a599")).toBe(false);
  });

  it("never throws when fetch throws synchronously", () => {
    fetchMock.mockImplementationOnce(() => {
      throw new Error("boom");
    });
    expect(() => reportTtsEvent("tts_started", "en", "x")).not.toThrow();
  });
});
