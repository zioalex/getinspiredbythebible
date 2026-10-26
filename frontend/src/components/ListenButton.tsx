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
  clearStartFailed,
  getPausedId,
  getSpeakingId,
  getStartFailedId,
  pause,
  resume,
  speak,
  stop,
  subscribe,
} from "@/lib/speech";

/** BITB-241: how long the "speech engine didn't respond" message stays visible. */
export const START_FAILED_NOTICE_MS = 6000;

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

  const startFailedId = useSyncExternalStore(
    subscribe,
    getStartFailedId,
    () => null,
  );
  const startFailed = startFailedId === messageId;

  // The message goes away on its own (the next tap clears it via speak()).
  useEffect(() => {
    if (!startFailed) return;
    const timer = setTimeout(clearStartFailed, START_FAILED_NOTICE_MS);
    return () => clearTimeout(timer);
  }, [startFailed]);

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
      {/* Always mounted (sr-only when empty) so the live region announces the change. Absolutely
          positioned against the sticky rail so the rail's width (and the answer) never reflows. */}
      <span
        role="status"
        className={
          startFailed
            ? "pointer-events-none absolute top-0 end-full me-1 z-10 w-28 rounded-md bg-white/95 p-1.5 text-center text-[11px] leading-tight text-amber-700 shadow dark:bg-gray-800/95 dark:text-amber-400"
            : "sr-only"
        }
      >
        {startFailed ? t("speechEngineNoResponse") : ""}
      </span>
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
