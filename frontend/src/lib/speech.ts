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
  /** BITB-249: strong references to this call's utterances (WebKit drops unreferenced ones). */
  utterances: SpeechSynthesisUtterance[];
}
let current: CurrentCall | null = null;
/** True while the browser's own synthesis queue is paused via synth.pause(). */
let nativePaused = false;
let resumeWatchdog: ReturnType<typeof setTimeout> | null = null;
/** BITB-241: separate timer detecting an engine that never starts a freshly queued reading. */
let startWatchdog: ReturnType<typeof setTimeout> | null = null;
/** BITB-241: id of the answer whose reading never started (engine silent / errored), or null. */
let startFailedId: string | null = null;

/** How long a native resume may stay silent before falling back to chunk restart. */
export const RESUME_WATCHDOG_MS = 1000;

/** BITB-241: how long a fresh reading may stay silent (no start/boundary) before one retry. */
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

/** Id of the message whose reading never started (BITB-241), or null. */
export function getStartFailedId(): string | null {
  return startFailedId;
}

/** BITB-249: the utterances the active call is holding on to (test hook), empty when idle. */
export function getActiveUtterances(): readonly SpeechSynthesisUtterance[] {
  return current?.utterances ?? [];
}

/** True when the browser still holds a queue (speaking, pending or paused). */
function isEngineBusy(synth: SpeechSynthesis): boolean {
  return nativePaused || synth.speaking || synth.pending || synth.paused;
}

/**
 * Cancels the browser queue; a paused queue must also be resumed or it stays paused.
 * With `onlyIfBusy`, an idle engine is left alone: on Linux Firefox (speech-dispatcher) the
 * asynchronous cancel can swallow the utterance queued right after it (BITB-241).
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

/**
 * Speaks `call.chunks` from `fromIndex`, ONE chunk at a time, replacing whatever plays.
 * BITB-249: WebKit (every iOS browser) drops utterances queued behind the first and
 * garbage-collects ones the page does not reference, so chunk i+1 is only spoken from chunk i's
 * `onend`, and the call keeps references to its utterances while it is active.
 */
function startQueue(call: CurrentCall, fromIndex: number, attempt = 1): void {
  const synth = window.speechSynthesis;
  generation += 1;
  const mine = generation;
  clearWatchdog();
  clearStartWatchdog();
  // One voice at a time: switching answers always cancels; the first speak and a same-call
  // retry skip the cancel on an idle engine (it can swallow the next utterance, BITB-241).
  const switching = current !== null && current !== call;
  cancelQueue(synth, !switching);
  call.index = fromIndex;
  call.utterances = [];
  current = call;
  setState(call.id, null);
  let started = false;

  // BITB-241: the engine never started (no start/boundary/error): retry once, then give up.
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

  const speakChunk = (index: number, chunkAttempt: number) => {
    if (generation !== mine || current !== call) return;
    let chunkStarted = false;
    const markStarted = () => {
      started = true;
      chunkStarted = true;
      clearWatchdog();
      clearStartWatchdog();
    };
    clearStartWatchdog();
    // Armed for every chunk: one that never starts is retried, then given up (BITB-241/248).
    startWatchdog = setTimeout(() => {
      startWatchdog = null;
      if (generation !== mine || current !== call || chunkStarted) return;
      // Only events prove audio began: a hung speech-dispatcher (Snap Firefox) reports
      // speaking=true and pending=true immediately and never plays (BITB-248).
      if (chunkAttempt < 2) startQueue(call, index, chunkAttempt + 1);
      else giveUp();
    }, START_WATCHDOG_MS);

    const utterance = new window.SpeechSynthesisUtterance(call.chunks[index]);
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
    utterance.onend = () => {
      if (generation !== mine) return;
      markStarted(); // any chunk ending proves the engine ran
      if (index >= call.chunks.length - 1) {
        finish();
        return;
      }
      call.index = index + 1; // a pause before the next start resumes at the next chunk
      // A native pause() does not bump the generation: don't speak into the paused engine;
      // resume()'s watchdog restarts at call.index.
      if (nativePaused) return;
      speakChunk(index + 1, 1); // each chunk gets a fresh retry budget
    };
    utterance.onerror = () => {
      if (generation !== mine) return;
      if (started) finish();
      else giveUp(); // errored before anything played
    };
    call.utterances.push(utterance); // keep a reference: WebKit GCs unreferenced utterances
    synth.speak(utterance);
  };

  speakChunk(fromIndex, attempt);
}

/**
 * Speak `chunks` in order, one utterance at a time, replacing anything already speaking or paused.
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
  startQueue({ id, chunks, voice, lang, index: 0, utterances: [] }, 0);
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
