import { useEffect } from "react";
import { stop as stopSpeech } from "@/lib/speech";

/**
 * BITB-119: silences any answer being read aloud whenever `key` changes (and on
 * mount). Used with the conversation id so starting or switching a conversation
 * stops speech even though messages are keyed by index.
 */
export function useStopSpeechOnChange(key: unknown): void {
  useEffect(() => {
    stopSpeech();
  }, [key]);
}
