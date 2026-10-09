import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import {
  SHOW_LISTEN_KEY,
  getShowListen,
  setShowListen,
  useShowListenPreference,
} from "./ttsPreference";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("ttsPreference", () => {
  it("defaults to on", () => {
    expect(getShowListen()).toBe(true);
  });

  it("persists off and on", () => {
    setShowListen(false);
    expect(localStorage.getItem(SHOW_LISTEN_KEY)).toBe("false");
    expect(getShowListen()).toBe(false);
    setShowListen(true);
    expect(getShowListen()).toBe(true);
  });

  it("falls back to on when storage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getShowListen()).toBe(true);
  });

  it("does not throw when storage cannot be written", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => setShowListen(false)).not.toThrow();
  });

  it("the hook reflects changes made anywhere", () => {
    const { result } = renderHook(() => useShowListenPreference());
    expect(result.current).toBe(true);
    act(() => setShowListen(false));
    expect(result.current).toBe(false);
    act(() => setShowListen(true));
    expect(result.current).toBe(true);
  });
});
