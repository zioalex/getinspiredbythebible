/**
 * BITB-119: the "Show Listen button" user preference (default on).
 *
 * Persisted per browser in localStorage (try/catch — storage can be blocked, in which
 * case the default "on" applies). Components stay in sync through a custom event, and
 * other tabs through the native `storage` event.
 */
import { useSyncExternalStore } from "react";

export const SHOW_LISTEN_KEY = "voxquieta.showListen";
const CHANGE_EVENT = "voxquieta:showListenChanged";

export function getShowListen(): boolean {
  try {
    return localStorage.getItem(SHOW_LISTEN_KEY) !== "false";
  } catch {
    return true;
  }
}

export function setShowListen(value: boolean): void {
  try {
    localStorage.setItem(SHOW_LISTEN_KEY, value ? "true" : "false");
  } catch {
    // Storage unavailable — the change still applies for this page view below.
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** Reactive "Show Listen button" preference. Server render assumes the default (on). */
export function useShowListenPreference(): boolean {
  return useSyncExternalStore(subscribe, getShowListen, () => true);
}
