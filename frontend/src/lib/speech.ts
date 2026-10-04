/**
 * BITB-119: on-device speech synthesis controller (web).
 *
 * A module-level singleton over `window.speechSynthesis`, so exactly one answer is
 * ever spoken at a time. Only voices with `localService === true` are used — no text
 * is ever sent to a network speech service. SSR-safe: every window access is guarded.
 */

type Listener = () => void;

let speakingId: string | null = null;
let generation = 0;
const listeners = new Set<Listener>();

function notify(): void {
  listeners.forEach((l) => l());
}

function setSpeakingId(id: string | null): void {
  if (speakingId === id) return;
  speakingId = id;
  notify();
}

/** True when the browser exposes speech synthesis at all. */
export function isSpeechSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance === "function"
  );
}

function primaryTag(lang: string): string {
  return lang.toLowerCase().replace("_", "-").split("-")[0];
}

/**
 * The best on-device voice for `locale`, or null. Remote (cloud) voices are ignored.
 * Preference: exact language-tag match, then the engine's default voice, then first.
 */
export function findLocalVoice(locale: string): SpeechSynthesisVoice | null {
  if (!isSpeechSupported()) return null;
  const wanted = primaryTag(locale);
  const candidates = window.speechSynthesis
    .getVoices()
    .filter((v) => v.localService === true && primaryTag(v.lang) === wanted);
  if (candidates.length === 0) return null;
  const exact = candidates.find(
    (v) => v.lang.toLowerCase().replace("_", "-") === locale.toLowerCase(),
  );
  return exact ?? candidates.find((v) => v.default) ?? candidates[0];
}

/**
 * Resolves once the browser has populated its voice list (Chrome fills it
 * asynchronously and fires `voiceschanged`). Resolves anyway after `timeoutMs`
 * so a browser that never fires the event cannot leave the UI waiting.
 */
export function loadVoices(timeoutMs = 1500): Promise<void> {
  if (!isSpeechSupported()) return Promise.resolve();
  const synth = window.speechSynthesis;
  if (synth.getVoices().length > 0) return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      synth.removeEventListener("voiceschanged", done);
      resolve();
    };
    const timer = setTimeout(done, timeoutMs);
    synth.addEventListener("voiceschanged", done);
  });
}

/** Subscribe to speaking-state changes. Returns an unsubscribe function. */
export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Id of the message currently being spoken, or null. */
export function getSpeakingId(): string | null {
  return speakingId;
}

/** Stop any speech immediately. */
export function stop(): void {
  generation += 1;
  if (isSpeechSupported()) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      // ignore
    }
  }
  setSpeakingId(null);
}

/**
 * Speak `chunks` in order as one queue, replacing anything already speaking.
 * Must be called from a user gesture (iOS Safari requirement) — the Listen click.
 */
export function speak(
  id: string,
  chunks: string[],
  voice: SpeechSynthesisVoice,
  lang: string,
): void {
  if (!isSpeechSupported() || chunks.length === 0) return;
  const synth = window.speechSynthesis;

  generation += 1;
  const mine = generation;
  synth.cancel(); // one voice at a time
  setSpeakingId(id);

  const finish = () => {
    if (generation !== mine) return; // superseded by stop() / another speak()
    generation += 1;
    try {
      synth.cancel(); // drop whatever is still queued after an error
    } catch {
      // ignore
    }
    setSpeakingId(null);
  };

  chunks.forEach((chunk, index) => {
    const utterance = new window.SpeechSynthesisUtterance(chunk);
    utterance.voice = voice;
    utterance.lang = voice.lang || lang;
    if (index === chunks.length - 1) utterance.onend = finish;
    utterance.onerror = finish;
    synth.speak(utterance);
  });
}
