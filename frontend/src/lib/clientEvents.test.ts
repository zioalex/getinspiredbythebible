import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  __resetClientEventsForTest,
  reportClientEvent,
  reportTtsUnavailableOnce,
} from "./clientEvents";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  __resetClientEventsForTest();
  fetchMock = vi.fn(() => Promise.resolve({ ok: true } as Response));
  global.fetch = fetchMock as unknown as typeof fetch;
});

describe("reportClientEvent", () => {
  it("posts only {event, locale} to the client-events sink", () => {
    reportClientEvent("tts_started", "ko");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/client-events$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      event: "tts_started",
      locale: "ko",
    });
    expect(Object.keys(JSON.parse(init.body)).sort()).toEqual([
      "event",
      "locale",
    ]);
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
    expect(bodies).toEqual([
      { event: "tts_unavailable", locale: "hi" },
      { event: "tts_unavailable", locale: "ar" },
    ]);
  });
});
