"use client";

import { useEffect } from "react";

export const CHAT_VIEWPORT_VAR = "--chat-viewport-height";

// Below this shrink (px) we treat a visual-viewport change as browser chrome
// (URL bar collapse, pinch-zoom jitter) rather than an on-screen keyboard.
const KEYBOARD_THRESHOLD_PX = 100;

/**
 * Keeps the chat shell sized to the *visible* area while an on-screen
 * keyboard is open (#1224).
 *
 * Android Chrome resizes the layout viewport itself (viewport meta
 * `interactive-widget=resizes-content`), so `100dvh` already shrinks there.
 * iOS Safari/Chrome ignore that hint: the keyboard only shrinks the visual
 * viewport and the browser scrolls the whole page to reveal the focused
 * input, pushing the header off screen. While the keyboard is open this hook
 * publishes the visual viewport height as `--chat-viewport-height` (the chat
 * <main> uses it, falling back to 100dvh) and pins the document scroll to the
 * top, so the composer sits right above the keyboard and only the message
 * list scrolls. When the keyboard closes the variable is removed.
 */
export function useKeyboardAwareViewport(): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const vv = window.visualViewport;
    if (!vv) return;
    const root = document.documentElement;

    const update = () => {
      const keyboardOpen =
        window.innerHeight - vv.height > KEYBOARD_THRESHOLD_PX &&
        // Pinch-zoom also shrinks the visual viewport; don't fight it.
        vv.scale <= 1.01;
      if (keyboardOpen) {
        root.style.setProperty(CHAT_VIEWPORT_VAR, `${Math.round(vv.height)}px`);
        if (window.scrollY !== 0) window.scrollTo(0, 0);
      } else {
        root.style.removeProperty(CHAT_VIEWPORT_VAR);
      }
    };

    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
      root.style.removeProperty(CHAT_VIEWPORT_VAR);
    };
  }, []);
}
