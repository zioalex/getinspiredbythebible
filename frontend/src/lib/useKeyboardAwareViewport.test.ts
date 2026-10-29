import { renderHook } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  CHAT_VIEWPORT_VAR,
  useKeyboardAwareViewport,
} from "./useKeyboardAwareViewport";

// #1224: keep the chat composer above the iOS on-screen keyboard.
class FakeVisualViewport extends EventTarget {
  height = 800;
  scale = 1;
}

describe("useKeyboardAwareViewport", () => {
  let vv: FakeVisualViewport;
  const root = document.documentElement;

  beforeEach(() => {
    vv = new FakeVisualViewport();
    Object.defineProperty(window, "visualViewport", {
      configurable: true,
      value: vv,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 800,
    });
    window.scrollTo = vi.fn();
    root.style.removeProperty(CHAT_VIEWPORT_VAR);
  });

  afterEach(() => {
    Object.defineProperty(window, "visualViewport", {
      configurable: true,
      value: undefined,
    });
  });

  it("does nothing while the keyboard is closed", () => {
    renderHook(() => useKeyboardAwareViewport());
    expect(root.style.getPropertyValue(CHAT_VIEWPORT_VAR)).toBe("");
  });

  it("publishes the visual viewport height when the keyboard opens", () => {
    renderHook(() => useKeyboardAwareViewport());
    vv.height = 450;
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 120,
    });
    vv.dispatchEvent(new Event("resize"));
    expect(root.style.getPropertyValue(CHAT_VIEWPORT_VAR)).toBe("450px");
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);
  });

  it("clears the variable when the keyboard closes", () => {
    renderHook(() => useKeyboardAwareViewport());
    vv.height = 450;
    vv.dispatchEvent(new Event("resize"));
    vv.height = 800;
    vv.dispatchEvent(new Event("resize"));
    expect(root.style.getPropertyValue(CHAT_VIEWPORT_VAR)).toBe("");
  });

  it("ignores small changes (collapsing browser toolbars)", () => {
    renderHook(() => useKeyboardAwareViewport());
    vv.height = 740;
    vv.dispatchEvent(new Event("resize"));
    expect(root.style.getPropertyValue(CHAT_VIEWPORT_VAR)).toBe("");
  });

  it("ignores pinch-zoom", () => {
    renderHook(() => useKeyboardAwareViewport());
    vv.height = 400;
    vv.scale = 2;
    vv.dispatchEvent(new Event("resize"));
    expect(root.style.getPropertyValue(CHAT_VIEWPORT_VAR)).toBe("");
  });

  it("removes the variable and listeners on unmount", () => {
    const { unmount } = renderHook(() => useKeyboardAwareViewport());
    vv.height = 450;
    vv.dispatchEvent(new Event("resize"));
    unmount();
    expect(root.style.getPropertyValue(CHAT_VIEWPORT_VAR)).toBe("");
    vv.dispatchEvent(new Event("resize"));
    expect(root.style.getPropertyValue(CHAT_VIEWPORT_VAR)).toBe("");
  });
});
