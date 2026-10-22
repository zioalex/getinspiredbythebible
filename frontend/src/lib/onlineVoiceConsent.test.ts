import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import {
  ONLINE_VOICES_KEY,
  getOnlineVoiceConsent,
  setOnlineVoiceConsent,
  useOnlineVoiceConsent,
} from "./onlineVoiceConsent";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("onlineVoiceConsent (BITB-210)", () => {
  it("is unset by default", () => {
    expect(getOnlineVoiceConsent()).toBe("unset");
  });

  it("persists granted and denied", () => {
    setOnlineVoiceConsent("granted");
    expect(localStorage.getItem(ONLINE_VOICES_KEY)).toBe("granted");
    expect(getOnlineVoiceConsent()).toBe("granted");
    setOnlineVoiceConsent("denied");
    expect(getOnlineVoiceConsent()).toBe("denied");
  });

  it("treats unknown stored values as unset", () => {
    localStorage.setItem(ONLINE_VOICES_KEY, "maybe");
    expect(getOnlineVoiceConsent()).toBe("unset");
  });

  it("falls back to unset when storage throws, and does not throw on write", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getOnlineVoiceConsent()).toBe("unset");
    expect(() => setOnlineVoiceConsent("granted")).not.toThrow();
  });

  it("the hook follows changes in this tab and via storage events", () => {
    const { result } = renderHook(() => useOnlineVoiceConsent());
    expect(result.current).toBe("unset");
    act(() => setOnlineVoiceConsent("granted"));
    expect(result.current).toBe("granted");
    act(() => {
      localStorage.setItem(ONLINE_VOICES_KEY, "denied");
      window.dispatchEvent(new Event("storage"));
    });
    expect(result.current).toBe("denied");
  });
});
