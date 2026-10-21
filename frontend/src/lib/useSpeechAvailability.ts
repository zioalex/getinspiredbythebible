"use client";

import { useEffect, useState } from "react";
import { findLocalVoice, isSpeechSupported, loadVoices } from "./speech";

export interface SpeechAvailability {
  /** The on-device voice for the locale, or null if none (yet). */
  voice: SpeechSynthesisVoice | null;
  /** True once the browser's voice list has been read (so "no voice" is final). */
  ready: boolean;
}

/**
 * Finds an on-device voice for `locale`, re-evaluating when the browser's voice list
 * changes. A no-op (never touches speechSynthesis) while `enabled` is false.
 */
export function useSpeechAvailability(
  locale: string,
  enabled: boolean,
): SpeechAvailability {
  const [state, setState] = useState<SpeechAvailability>({
    voice: null,
    ready: false,
  });

  useEffect(() => {
    if (!enabled) {
      setState({ voice: null, ready: false });
      return;
    }
    if (!isSpeechSupported()) {
      setState({ voice: null, ready: true });
      return;
    }
    let cancelled = false;
    const synth = window.speechSynthesis;
    const refresh = () => {
      if (!cancelled) setState({ voice: findLocalVoice(locale), ready: true });
    };
    void loadVoices().then(refresh);
    synth.addEventListener("voiceschanged", refresh);
    return () => {
      cancelled = true;
      synth.removeEventListener("voiceschanged", refresh);
    };
  }, [locale, enabled]);

  return state;
}
