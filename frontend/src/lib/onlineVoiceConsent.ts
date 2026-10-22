/**
 * BITB-210: per-device consent to use the browser's online speech voices.
 *
 * Offline voices are the default (BITB-119: no answer text leaves the device). When a
 * browser only has online voices for the UI language, speaking with one sends the answer
 * text to the browser vendor's speech service, so it needs an explicit opt-in. Persisted
 * per browser in localStorage (try/catch — storage can be blocked, in which case the
 * choice is "unset" and the dialog is shown again). Mirrors `ttsPreference.ts`.
 */
import { useSyncExternalStore } from "react";

export const ONLINE_VOICES_KEY = "voxquieta.onlineVoices";
const CHANGE_EVENT = "voxquieta:onlineVoicesChanged";

/** Fallback for this page view when storage is blocked, so the choice still sticks. */
let memoryValue: OnlineVoiceConsent = "unset";
let storageBlocked = false;

/** Test helper: forget the in-memory fallback. */
export function __resetOnlineVoiceConsentForTest(): void {
  memoryValue = "unset";
  storageBlocked = false;
}

export type OnlineVoiceConsent = "granted" | "denied" | "unset";

export function getOnlineVoiceConsent(): OnlineVoiceConsent {
  try {
    const value = localStorage.getItem(ONLINE_VOICES_KEY);
    if (storageBlocked) return memoryValue;
    return value === "granted" || value === "denied" ? value : "unset";
  } catch {
    return memoryValue;
  }
}

export function setOnlineVoiceConsent(value: "granted" | "denied"): void {
  memoryValue = value;
  try {
    localStorage.setItem(ONLINE_VOICES_KEY, value);
    storageBlocked = false;
  } catch {
    storageBlocked = true;
    // Storage unavailable — the in-memory value keeps the choice for this page view.
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

/** Reactive online-voice consent. Server render assumes "unset". */
export function useOnlineVoiceConsent(): OnlineVoiceConsent {
  return useSyncExternalStore(
    subscribe,
    getOnlineVoiceConsent,
    (): OnlineVoiceConsent => "unset",
  );
}
