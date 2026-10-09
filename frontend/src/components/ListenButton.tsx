"use client";

import { useEffect, useSyncExternalStore } from "react";
import { Square, Volume2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useServerConfig } from "@/lib/serverConfig";
import { useShowListenPreference } from "@/lib/ttsPreference";
import { useSpeechAvailability } from "@/lib/useSpeechAvailability";
import { speakableChunks } from "@/lib/speakableText";
import {
  reportClientEvent,
  reportTtsUnavailableOnce,
} from "@/lib/clientEvents";
import { getSpeakingId, speak, stop, subscribe } from "@/lib/speech";

interface ListenButtonProps {
  /** Identifies the message so only one answer is spoken at a time. */
  messageId: string;
  /** Raw assistant markdown (normalized for speech here, never linkified text). */
  content: string;
}

/**
 * BITB-119: Listen <-> Stop toggle for a finished assistant answer, using on-device
 * speech only. Renders nothing unless the server flag is not explicitly off, the user
 * preference is on, and a local voice exists for the UI language — never
 * shown-and-broken.
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
  const { voice, ready } = useSpeechAvailability(locale, prerequisitesMet);
  const speakingId = useSyncExternalStore(subscribe, getSpeakingId, () => null);

  const hasContent = content.trim().length > 0;
  const visible = prerequisitesMet && voice !== null && hasContent;
  const isSpeaking = speakingId === messageId;

  // Flag + preference are on but this browser has no local voice: count it (once).
  useEffect(() => {
    if (prerequisitesMet && ready && voice === null) {
      reportTtsUnavailableOnce(locale);
    }
  }, [prerequisitesMet, ready, voice, locale]);

  // Stop when this message unmounts or the language changes while it is speaking.
  useEffect(
    () => () => {
      if (getSpeakingId() === messageId) stop();
    },
    [messageId, locale],
  );

  // Hiding the control (preference off, flag off) must also silence it.
  useEffect(() => {
    if (!visible && getSpeakingId() === messageId) stop();
  }, [visible, messageId]);

  if (!visible || !voice) return null;

  const label = isSpeaking ? t("stopListening") : t("listenAnswer");

  const handleClick = () => {
    if (isSpeaking) {
      stop();
      return;
    }
    const chunks = speakableChunks(content, locale);
    if (chunks.length === 0) return;
    speak(messageId, chunks, voice, locale);
    reportClientEvent("tts_started", locale);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={label}
      aria-pressed={isSpeaking}
      title={label}
      className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] p-1.5 rounded-lg text-gray-400 hover:text-primary-600 hover:bg-primary-50 transition-colors aria-pressed:text-primary-600"
    >
      {isSpeaking ? (
        <Square className="w-4 h-4" aria-hidden="true" />
      ) : (
        <Volume2 className="w-4 h-4" aria-hidden="true" />
      )}
    </button>
  );
}
