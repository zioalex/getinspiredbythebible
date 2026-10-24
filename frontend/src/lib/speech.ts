/**
 * BITB-119: on-device speech synthesis controller (web).
 *
 * A module-level singleton over `window.speechSynthesis`, so exactly one answer is
 * ever spoken at a time. Offline voices (`localService === true`) are the default — no text
 * is sent to a network speech service; online voices are used only after the per-device
 * opt-in (BITB-210). SSR-safe: every window access is guarded.
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
/** BITB-238: separate timer detecting an engine that never starts a freshly queued reading. */
let startWatchdog: ReturnType<typeof setTimeout> | null = null;
/** BITB-238: id of the answer whose reading never started (engine silent / errored), or null. */
let startFailedId: string | null = null;

/** How long a native resume may stay silent before falling back to chunk restart. */
export const RESUME_WATCHDOG_MS = 1000;

/** BITB-238: how long a fresh reading may stay silent (no start/boundary) before one retry. */
export const START_WATCHDOG_MS = 3000;

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

function clearStartWatchdog(): void {
  if (startWatchdog !== null) {
    clearTimeout(startWatchdog);
    startWatchdog = null;
  }
}

/** Forget a recorded start failure (next speak/stop, or when the UI hides its message). */
export function clearStartFailed(): void {
  if (startFailedId === null) return;
  startFailedId = null;
  notify();
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
 * Picks the best of `candidates` (already filtered to the locale's language).
 * Preference: exact language-tag match, the locale's regional default (e.g. zh-CN), the
 * engine's default voice, then first.
 */
function rankVoice(
  candidates: SpeechSynthesisVoice[],
  locale: string,
): SpeechSynthesisVoice | null {
  if (candidates.length === 0) return null;
  const exact = candidates.find(
    (v) => normalizeTag(v.lang) === normalizeTag(locale),
  );
  if (exact) return exact;
  const regionDefault = REGION_DEFAULTS[primaryTag(locale)];
  const regional = regionDefault
    ? candidates.find((v) => normalizeTag(v.lang) === regionDefault)
    : undefined;
  return regional ?? candidates.find((v) => v.default) ?? candidates[0];
}

function voicesFor(locale: string, local: boolean): SpeechSynthesisVoice[] {
  const wanted = primaryTag(locale);
  return window.speechSynthesis
    .getVoices()
    .filter(
      (v) =>
        (v.localService === true) === local && primaryTag(v.lang) === wanted,
    );
}

/** The best on-device voice for `locale`, or null. Remote (cloud) voices are ignored. */
export function findLocalVoice(locale: string): SpeechSynthesisVoice | null {
  if (!isSpeechSupported()) return null;
  return rankVoice(voicesFor(locale, true), locale);
}

/**
 * BITB-210: the best online (`localService === false`) voice for `locale`, or null. Speaking
 * with it sends the text to the browser vendor's speech service, so callers must only use it
 * after the user's per-device opt-in (`onlineVoiceConsent.ts`).
 */
export function findOnlineVoice(locale: string): SpeechSynthesisVoice | null {
  if (!isSpeechSupported()) return null;
  return rankVoice(voicesFor(locale, false), locale);
}

/** BITB-210: which kind of voice this browser offers for a locale; an offline voice wins. */
export type VoiceAvailability = "local" | "online" | "none";

export function voiceAvailability(locale: string): VoiceAvailability {
  if (findLocalVoice(locale)) return "local";
  return findOnlineVoice(locale) ? "online" : "none";
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

/** Id of the message whose reading never started (BITB-238), or null. */
export function getStartFailedId(): string | null {
  return startFailedId;
}

/** True when the browser still holds a queue (speaking, pending or paused). */
function isEngineBusy(synth: SpeechSynthesis): boolean {
  return nativePaused || synth.speaking || synth.pending || synth.paused;
}

/**
 * Cancels the browser queue; a paused queue must also be resumed or it stays paused.
 * With `onlyIfBusy`, an idle engine is left alone: on Linux Firefox (speech-dispatcher) the
 * asynchronous cancel can swallow the utterance queued right after it (BITB-238).
 */
function cancelQueue(synth: SpeechSynthesis, onlyIfBusy = false): void {
  if (onlyIfBusy && !isEngineBusy(synth)) {
    nativePaused = false;
    return;
  }
  try {
    synth.cancel();
    // A native resume() can silently no-op (Chrome), leaving the engine paused.
    if (nativePaused || synth.paused) synth.resume();
  } catch {
    // ignore
  }
  nativePaused = false;
}

/** Stop any speech immediately and forget any paused position. */
export function stop(): void {
  const hadReading = speakingId !== null || pausedId !== null;
  generation += 1;
  clearWatchdog();
  clearStartWatchdog();
  const hadFailure = startFailedId !== null;
  startFailedId = null;
  if (isSpeechSupported()) {
    // Our own reading may not be visible in the browser's flags yet, so cancel for it too.
    cancelQueue(window.speechSynthesis, !hadReading);
  }
  current = null;
  nativePaused = false;
  setState(null, null);
  if (hadFailure) notify();
}

/** Queues `call.chunks` from `fromIndex` as one fresh queue, replacing whatever plays. */
function startQueue(call: CurrentCall, fromIndex: number, attempt = 1): void {
  const synth = window.speechSynthesis;
  generation += 1;
  const mine = generation;
  clearWatchdog();
  clearStartWatchdog();
  // One voice at a time: switching answers always cancels; the first speak and a same-call
  // retry skip the cancel on an idle engine (it can swallow the next utterance, BITB-238).
  const switching = current !== null && current !== call;
  cancelQueue(synth, !switching);
  call.index = fromIndex;
  current = call;
  setState(call.id, null);
  let started = false;

  // BITB-238: the engine never started (no start/boundary/error): retry once, then give up.
  const giveUp = () => {
    generation += 1;
    clearWatchdog();
    clearStartWatchdog();
    try {
      if (isEngineBusy(synth)) synth.cancel();
    } catch {
      // ignore
    }
    current = null;
    nativePaused = false;
    startFailedId = call.id;
    const stateChanged = speakingId !== null || pausedId !== null;
    setState(null, null);
    if (!stateChanged) notify(); // otherwise setState already notified
  };
  const markStarted = () => {
    started = true;
    clearWatchdog();
    clearStartWatchdog();
  };
  startWatchdog = setTimeout(() => {
    startWatchdog = null;
    if (generation !== mine || current !== call || started) return;
    // Firefox only sets `speaking` after a real start, so it proves audio began.
    if (synth.speaking) {
      started = true;
      return;
    }
    if (attempt < 2) startQueue(call, fromIndex, attempt + 1);
    else giveUp();
  }, START_WATCHDOG_MS);

  const finish = () => {
    if (generation !== mine) return; // superseded by stop() / pause() / another speak()
    generation += 1;
    clearWatchdog();
    clearStartWatchdog();
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
      markStarted();
    };
    // A silent native resume is detected by the absence of any of these.
    utterance.onresume = () => {
      if (generation === mine) clearWatchdog();
    };
    utterance.onboundary = () => {
      if (generation === mine) markStarted();
    };
    // Any chunk ending proves the engine ran.
    utterance.onend =
      index === call.chunks.length - 1
        ? finish
        : () => {
            if (generation === mine) markStarted();
          };
    utterance.onerror = () => {
      if (generation !== mine) return;
      if (started) finish();
      else giveUp(); // errored before anything played
    };
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
  clearStartFailed();
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
  clearStartWatchdog();
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
