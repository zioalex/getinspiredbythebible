"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { Pause, Play, Volume2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useServerConfig } from "@/lib/serverConfig";
import OnlineVoiceConsentDialog from "@/components/OnlineVoiceConsentDialog";
import {
  setOnlineVoiceConsent,
  useOnlineVoiceConsent,
} from "@/lib/onlineVoiceConsent";
import { useShowListenPreference } from "@/lib/ttsPreference";
import { useSpeechAvailability } from "@/lib/useSpeechAvailability";
import { speakableChunks } from "@/lib/speakableText";
import {
  reportClientEvent,
  reportTtsUnavailableOnce,
} from "@/lib/clientEvents";
import {
  getPausedId,
  getSpeakingId,
  pause,
  resume,
  speak,
  stop,
  subscribe,
} from "@/lib/speech";

interface ListenButtonProps {
  /** Identifies the message so only one answer is spoken at a time. */
  messageId: string;
  /** Raw assistant markdown (normalized for speech here, never linkified text). */
  content: string;
}

/**
 * BITB-119 / BITB-205: Listen / Pause / Resume control for a finished assistant answer.
 * Renders nothing unless the server flag is not explicitly off, the user preference is on,
 * and a usable voice exists for the UI language — never shown-and-broken.
 *
 * BITB-210: an offline voice always wins. With only an online voice, the first tap asks for
 * a per-device opt-in (the answer text goes to the browser's speech service); "Not now" hides
 * the button, and revoking consent in the menu stops any online reading.
 */
export default function ListenButton({
  messageId,
  content,
}: ListenButtonProps) {
  const t = useTranslations("Chat");
  const locale = useLocale();
  const { ttsEnabled } = useServerConfig();
  const showPreference = useShowListenPreference();
  const prerequisitesMet = ttsEnabled && showPreference;
  const {
    voice: localVoice,
    onlineVoice,
    availability,
    ready,
  } = useSpeechAvailability(locale, prerequisitesMet);
  const consent = useOnlineVoiceConsent();
  const [dialogOpen, setDialogOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const speakingId = useSyncExternalStore(subscribe, getSpeakingId, () => null);
  const pausedId = useSyncExternalStore(subscribe, getPausedId, () => null);

  const hasContent = content.trim().length > 0;
  // Offline voice first; an online voice only after the user's opt-in.
  const voice = localVoice ?? (consent === "granted" ? onlineVoice : null);
  const needsConsent =
    voice === null && availability === "online" && consent === "unset";
  const visible =
    prerequisitesMet && (voice !== null || needsConsent) && hasContent;
  const isSpeaking = speakingId === messageId;
  const isPaused = pausedId === messageId;

  // Consent changed elsewhere (another tab): drop a stale dialog so it cannot reappear.
  useEffect(() => {
    if (!needsConsent) setDialogOpen(false);
  }, [needsConsent]);

  // Flag + preference are on but this browser has no voice at all for the language: count it
  // (once). An online-only browser is not "unavailable" — the opt-in covers it (BITB-210).
  useEffect(() => {
    if (prerequisitesMet && ready && availability === "none") {
      reportTtsUnavailableOnce(locale);
    }
  }, [prerequisitesMet, ready, availability, locale]);

  // Stop (and drop a paused position) when this message unmounts or the language changes
  // while it is speaking or paused.
  useEffect(
    () => () => {
      if (getSpeakingId() === messageId || getPausedId() === messageId) stop();
    },
    [messageId, locale],
  );

  // Hiding the control (preference off, flag off) must also silence it.
  useEffect(() => {
    if (
      !visible &&
      (getSpeakingId() === messageId || getPausedId() === messageId)
    ) {
      stop();
    }
  }, [visible, messageId]);

  if (!visible) return null;

  const label = isSpeaking
    ? t("pauseListening")
    : isPaused
      ? t("resumeListening")
      : t("listenAnswer");

  const startSpeaking = (withVoice: SpeechSynthesisVoice) => {
    const chunks = speakableChunks(content, locale);
    if (chunks.length === 0) return;
    speak(messageId, chunks, withVoice, locale);
    reportClientEvent("tts_started", locale);
  };

  const handleAllow = () => {
    setOnlineVoiceConsent("granted");
    setDialogOpen(false);
    // Still inside the click gesture (iOS Safari requirement).
    if (onlineVoice) startSpeaking(onlineVoice);
  };

  const handleDecline = () => {
    // Declining unmounts this button, which would drop focus to <body>; hand it to the
    // next control in the action rail (e.g. Share) once the removal has happened.
    const self = buttonRef.current;
    const next = self?.parentElement
      ? Array.from(
          self.parentElement.querySelectorAll<HTMLElement>("button, a[href]"),
        ).find((el) => el !== self)
      : undefined;
    setOnlineVoiceConsent("denied");
    if (next) {
      setTimeout(() => {
        const active = document.activeElement;
        if (!active || active === document.body) next.focus();
      }, 0);
    }
    setDialogOpen(false);
  };

  const handleClick = () => {
    if (!voice) {
      setDialogOpen(true);
      return;
    }
    if (isSpeaking) {
      pause();
      return;
    }
    if (isPaused) {
      resume(); // does not re-send tts_started
      return;
    }
    startSpeaking(voice);
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={handleClick}
        aria-label={label}
        aria-pressed={isSpeaking}
        data-state={isSpeaking ? "playing" : isPaused ? "paused" : "idle"}
        title={label}
        className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] p-1.5 rounded-lg text-gray-400 hover:text-primary-600 hover:bg-primary-50 transition-colors aria-pressed:text-primary-600 data-[state=paused]:text-primary-600"
      >
        {isSpeaking ? (
          <Pause className="w-4 h-4" aria-hidden="true" />
        ) : isPaused ? (
          <Play className="w-4 h-4" aria-hidden="true" />
        ) : (
          <Volume2 className="w-4 h-4" aria-hidden="true" />
        )}
      </button>
      {/* Portal: the sticky action rail is a stacking context that would trap z-50. */}
      {dialogOpen &&
        needsConsent &&
        createPortal(
          <OnlineVoiceConsentDialog
            onAllow={handleAllow}
            onDecline={handleDecline}
            returnFocusTo={buttonRef}
          />,
          document.body,
        )}
    </>
  );
}
