"use client";

import { useEffect, useState } from "react";
import {
  findLocalVoice,
  findOnlineVoice,
  isSpeechSupported,
  loadVoices,
  type VoiceAvailability,
} from "./speech";

export interface SpeechAvailability {
  /** The on-device voice for the locale, or null if none (yet). */
  voice: SpeechSynthesisVoice | null;
  /** BITB-210: the best online voice for the locale, or null. Needs the user's opt-in to use. */
  onlineVoice: SpeechSynthesisVoice | null;
  /** BITB-210: local (offline voice wins), online (online voice only) or none. */
  availability: VoiceAvailability;
  /** True once the browser's voice list has been read (so "no voice" is final). */
  ready: boolean;
}

const EMPTY: SpeechAvailability = {
  voice: null,
  onlineVoice: null,
  availability: "none",
  ready: false,
};

/**
 * Finds the voices for `locale`, re-evaluating when the browser's voice list
 * changes. A no-op (never touches speechSynthesis) while `enabled` is false.
 */
export function useSpeechAvailability(
  locale: string,
  enabled: boolean,
): SpeechAvailability {
  const [state, setState] = useState<SpeechAvailability>(EMPTY);

  useEffect(() => {
    if (!enabled) {
      setState(EMPTY);
      return;
    }
    if (!isSpeechSupported()) {
      setState({ ...EMPTY, ready: true });
      return;
    }
    let cancelled = false;
    const synth = window.speechSynthesis;
    const refresh = () => {
      if (cancelled) return;
      const voice = findLocalVoice(locale);
      const onlineVoice = findOnlineVoice(locale);
      setState({
        voice,
        onlineVoice,
        availability: voice ? "local" : onlineVoice ? "online" : "none",
        ready: true,
      });
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
