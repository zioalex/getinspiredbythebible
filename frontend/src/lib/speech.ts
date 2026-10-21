/**
 * BITB-119: on-device speech synthesis controller (web).
 *
 * A module-level singleton over `window.speechSynthesis`, so exactly one answer is
 * ever spoken at a time. Only voices with `localService === true` are used — no text
 * is ever sent to a network speech service. SSR-safe: every window access is guarded.
 */

type Listener = () => void;

let speakingId: string | null = null;
/** BITB-205: id of the answer whose reading is paused (position kept), or null. */
let pausedId: string | null = null;
let generation = 0;
const listeners = new Set<Listener>();

/** The call being spoken or paused; kept so a paused reading can continue (BITB-205). */
interface CurrentCall {
  id: string;
  chunks: string[];
  voice: SpeechSynthesisVoice;
  lang: string;
  /** Index of the chunk that is playing (set from utterance.onstart). */
  index: number;
}
let current: CurrentCall | null = null;
/** True while the browser's own synthesis queue is paused via synth.pause(). */
let nativePaused = false;
let resumeWatchdog: ReturnType<typeof setTimeout> | null = null;

/** How long a native resume may stay silent before falling back to chunk restart. */
export const RESUME_WATCHDOG_MS = 1000;

function notify(): void {
  listeners.forEach((l) => l());
}

function setState(speaking: string | null, paused: string | null): void {
  if (speakingId === speaking && pausedId === paused) return;
  speakingId = speaking;
  pausedId = paused;
  notify();
}

function clearWatchdog(): void {
  if (resumeWatchdog !== null) {
    clearTimeout(resumeWatchdog);
    resumeWatchdog = null;
  }
}

/** Android Chrome's synth.pause() is unreliable (it cancels), so use chunk restart there. */
function shouldUseNativePause(): boolean {
  return (
    typeof navigator === "undefined" || !/Android/i.test(navigator.userAgent)
  );
}

/** True when the browser exposes speech synthesis at all. */
export function isSpeechSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance === "function"
  );
}

/** Regional default per UI locale, preferred over arbitrary same-language voices. */
const REGION_DEFAULTS: Record<string, string> = {
  en: "en-us",
  es: "es-es",
  pt: "pt-br",
  fr: "fr-fr",
  de: "de-de",
  ar: "ar-sa",
  ko: "ko-kr",
  hi: "hi-in",
  ru: "ru-ru",
  it: "it-it",
  zh: "zh-cn",
};

function normalizeTag(lang: string): string {
  return lang.toLowerCase().replace("_", "-");
}

function primaryTag(lang: string): string {
  return lang.toLowerCase().replace("_", "-").split("-")[0];
}

/**
 * The best on-device voice for `locale`, or null. Remote (cloud) voices are ignored.
 * Preference: exact language-tag match, the locale's regional default (e.g. zh-CN), the
 * engine's default voice, then first.
 */
export function findLocalVoice(locale: string): SpeechSynthesisVoice | null {
  if (!isSpeechSupported()) return null;
  const wanted = primaryTag(locale);
  const candidates = window.speechSynthesis
    .getVoices()
    .filter((v) => v.localService === true && primaryTag(v.lang) === wanted);
  if (candidates.length === 0) return null;
  const exact = candidates.find(
    (v) => normalizeTag(v.lang) === normalizeTag(locale),
  );
  if (exact) return exact;
  const regionDefault = REGION_DEFAULTS[wanted];
  const regional = regionDefault
    ? candidates.find((v) => normalizeTag(v.lang) === regionDefault)
    : undefined;
  return regional ?? candidates.find((v) => v.default) ?? candidates[0];
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

/** Id of the message whose reading is paused (BITB-205), or null. */
export function getPausedId(): string | null {
  return pausedId;
}

/** Cancels the browser queue; a natively paused queue must also be resumed or it stays paused. */
function cancelQueue(synth: SpeechSynthesis): void {
  try {
    synth.cancel();
    if (nativePaused) synth.resume();
  } catch {
    // ignore
  }
  nativePaused = false;
}

/** Stop any speech immediately and forget any paused position. */
export function stop(): void {
  generation += 1;
  clearWatchdog();
  if (isSpeechSupported()) cancelQueue(window.speechSynthesis);
  current = null;
  nativePaused = false;
  setState(null, null);
}

/** Queues `call.chunks` from `fromIndex` as one fresh queue, replacing whatever plays. */
function startQueue(call: CurrentCall, fromIndex: number): void {
  const synth = window.speechSynthesis;
  generation += 1;
  const mine = generation;
  clearWatchdog();
  cancelQueue(synth); // one voice at a time
  call.index = fromIndex;
  current = call;
  setState(call.id, null);

  const finish = () => {
    if (generation !== mine) return; // superseded by stop() / pause() / another speak()
    generation += 1;
    clearWatchdog();
    try {
      synth.cancel(); // drop whatever is still queued after an error
    } catch {
      // ignore
    }
    current = null;
    setState(null, null);
  };

  call.chunks.forEach((chunk, index) => {
    if (index < fromIndex) return;
    const utterance = new window.SpeechSynthesisUtterance(chunk);
    utterance.voice = call.voice;
    utterance.lang = call.voice.lang || call.lang;
    utterance.onstart = () => {
      if (generation !== mine) return;
      call.index = index;
      clearWatchdog();
    };
    // A silent native resume is detected by the absence of any of these.
    utterance.onresume = () => {
      if (generation === mine) clearWatchdog();
    };
    utterance.onboundary = () => {
      if (generation === mine) clearWatchdog();
    };
    if (index === call.chunks.length - 1) utterance.onend = finish;
    utterance.onerror = finish;
    synth.speak(utterance);
  });
}

/**
 * Speak `chunks` in order as one queue, replacing anything already speaking or paused.
 * Must be called from a user gesture (iOS Safari requirement) — the Listen click.
 */
export function speak(
  id: string,
  chunks: string[],
  voice: SpeechSynthesisVoice,
  lang: string,
): void {
  if (!isSpeechSupported() || chunks.length === 0) return;
  startQueue({ id, chunks, voice, lang, index: 0 }, 0);
}

/**
 * BITB-205: pause the current reading, keeping its position. Native `speechSynthesis.pause()`
 * keeps the exact spot; on Android Chrome (where it is unreliable) the queue is cancelled and
 * `resume()` restarts the chunk that was playing. No-op when nothing is speaking.
 */
export function pause(): void {
  if (!isSpeechSupported() || speakingId === null || current === null) return;
  const synth = window.speechSynthesis;
  clearWatchdog();
  if (shouldUseNativePause()) {
    try {
      synth.pause();
      nativePaused = true;
    } catch {
      nativePaused = false;
    }
  }
  if (!nativePaused) {
    generation += 1; // ignore the cancelled queue's callbacks
    cancelQueue(synth);
  }
  setState(null, current.id);
}

/**
 * BITB-205: continue a paused reading. Native resume continues mid-sentence; if the browser
 * stays silent for `RESUME_WATCHDOG_MS` (a known Chrome failure), or native pause was not
 * used, the remaining chunks are re-spoken starting at the chunk that was playing.
 */
export function resume(): boolean {
  if (!isSpeechSupported() || pausedId === null || current === null) {
    return false;
  }
  const call = current;
  if (!nativePaused) {
    startQueue(call, call.index);
    return true;
  }
  const synth = window.speechSynthesis;
  const mine = generation;
  try {
    synth.resume();
  } catch {
    // fall through to the watchdog restart below
  }
  nativePaused = false;
  setState(call.id, null);
  clearWatchdog();
  resumeWatchdog = setTimeout(() => {
    resumeWatchdog = null;
    if (generation !== mine || current !== call) return;
    startQueue(call, call.index);
  }, RESUME_WATCHDOG_MS);
  return true;
}
