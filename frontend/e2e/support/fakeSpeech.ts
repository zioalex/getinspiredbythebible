/**
 * BITB-250: a fake `speechSynthesis` for the read-aloud e2e spec.
 *
 * Real engines can't be driven in CI (no audio, no voices, and the interesting failures only
 * happen on specific browsers/OSes), so each known browser quirk is replayed by a profile of
 * this fake. It is installed with `page.addInitScript`, replacing `window.speechSynthesis` and
 * `window.SpeechSynthesisUtterance` before any app code runs, and records what was spoken so a
 * test can read it back with `getSpeechLog`.
 *
 * To add a profile for a new browser quirk, see e2e/README.md.
 */
import type { Page } from "@playwright/test";

export type FakeSpeechProfile =
  /** Realistic start/boundary/end events; local voices. */
  | "well-behaved"
  /** BITB-249: WebKit/iOS silently drops utterances queued while another is pending. */
  | "ios-webkit-drops-queue"
  /** BITB-248: hung speech-dispatcher; speaking/pending go true, no event ever fires. */
  | "hung-speechd"
  /** Chrome: getVoices() is empty until a delayed `voiceschanged`. */
  | "chrome-late-voices"
  /** Chrome/Firefox: cancel() synchronously fires onend on the current utterance. */
  | "cancel-fires-end"
  /** BITB-210: only `localService: false` voices. */
  | "online-only"
  /** An empty voice list. */
  | "no-voices";

export const FAKE_SPEECH_PROFILES: readonly FakeSpeechProfile[] = [
  "well-behaved",
  "ios-webkit-drops-queue",
  "hung-speechd",
  "chrome-late-voices",
  "cancel-fires-end",
  "online-only",
  "no-voices",
];

export interface FakeSpeechOptions {
  /** How long each chunk "plays" for, in ms (default 150). */
  chunkMs?: number;
  /** Delay before `chrome-late-voices` reports its voices, in ms (default 800). */
  lateVoicesMs?: number;
}

export interface SpeechLog {
  profile: FakeSpeechProfile;
  /** Every `speak()` call, in order, whether or not the engine honoured it. */
  queued: string[];
  /** Utterances whose `onstart` fired, in order: what the user actually heard. */
  spoken: string[];
  /** Name of the voice each entry of `spoken` was started with (same order). */
  spokenVoices: string[];
  /** Utterances the profile swallowed without ever firing an event. */
  dropped: string[];
  cancelCount: number;
  pauseCount: number;
  resumeCount: number;
}

interface InstallArgs {
  profile: FakeSpeechProfile;
  chunkMs: number;
  lateVoicesMs: number;
}

/** Installs the fake engine for every page/navigation of `page`'s context. */
export async function installFakeSpeech(
  page: Page,
  profile: FakeSpeechProfile,
  options: FakeSpeechOptions = {},
): Promise<void> {
  const args: InstallArgs = {
    profile,
    chunkMs: options.chunkMs ?? 150,
    lateVoicesMs: options.lateVoicesMs ?? 800,
  };
  await page.addInitScript(installInPage, args);
}

/** Reads the engine's log back out of the page. */
export async function getSpeechLog(page: Page): Promise<SpeechLog> {
  return page.evaluate(
    () => (window as unknown as { __fakeSpeech: SpeechLog }).__fakeSpeech,
  );
}

/**
 * Runs inside the browser (serialised by Playwright), so it must be fully self-contained: no
 * imports and no references to anything outside its own body.
 */
function installInPage(args: InstallArgs): void {
  const { profile, chunkMs, lateVoicesMs } = args;

  const log = {
    profile,
    queued: [] as string[],
    spoken: [] as string[],
    spokenVoices: [] as string[],
    dropped: [] as string[],
    cancelCount: 0,
    pauseCount: 0,
    resumeCount: 0,
  };
  Object.defineProperty(window, "__fakeSpeech", {
    value: log,
    configurable: true,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type AnyFn = (...a: any[]) => any;

  class FakeUtterance {
    text: string;
    lang = "";
    voice: unknown = null;
    rate = 1;
    pitch = 1;
    volume = 1;
    onstart: AnyFn | null = null;
    onend: AnyFn | null = null;
    onerror: AnyFn | null = null;
    onboundary: AnyFn | null = null;
    onpause: AnyFn | null = null;
    onresume: AnyFn | null = null;
    onmark: AnyFn | null = null;
    constructor(text?: string) {
      this.text = text === undefined ? "" : String(text);
    }
  }

  const voice = (name: string, lang: string, localService: boolean) => ({
    name,
    lang,
    localService,
    default: false,
    voiceURI: name,
  });
  const LOCAL_VOICES = [
    { ...voice("Fake English (US)", "en-US", true), default: true },
    voice("Fake English (UK)", "en-GB", true),
  ];
  const ONLINE_VOICES = [
    voice("Fake Online English (US)", "en-US", false),
    voice("Fake Online English (UK)", "en-GB", false),
  ];

  let voices: unknown[] =
    profile === "no-voices"
      ? []
      : profile === "online-only"
        ? ONLINE_VOICES
        : profile === "chrome-late-voices"
          ? []
          : LOCAL_VOICES;

  const target = new EventTarget();

  // Engine state ------------------------------------------------------------
  let current: FakeUtterance | null = null; // playing (or hung) right now
  let currentStarted = false; // has `current` fired onstart yet?
  const pendingQueue: FakeUtterance[] = [];
  let paused = false;
  let hungSpeaking = false; // hung-speechd: flags true, no events
  let timer: ReturnType<typeof setTimeout> | null = null;
  let remainingMs = 0;
  let timerStartedAt = 0;

  const fire = (u: FakeUtterance, kind: keyof FakeUtterance, ev: object) => {
    const handler = u[kind];
    if (typeof handler === "function") {
      try {
        (handler as AnyFn).call(u, { type: String(kind).slice(2), ...ev });
      } catch (e) {
        // A throwing app handler must not wedge the fake engine.
        console.error("fake speech handler threw", e);
      }
    }
  };

  const clearTimer = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  };

  const finishCurrent = () => {
    const u = current;
    clearTimer();
    current = null;
    currentStarted = false;
    if (!u) return;
    fire(u, "onend", { charIndex: u.text.length, elapsedTime: chunkMs });
    playNext();
  };

  const scheduleEnd = (ms: number) => {
    remainingMs = ms;
    timerStartedAt = Date.now();
    timer = setTimeout(finishCurrent, ms);
  };

  const startCurrent = (u: FakeUtterance) => {
    if (current !== u || paused || currentStarted) return;
    currentStarted = true;
    log.spoken.push(u.text);
    log.spokenVoices.push((u.voice as { name?: string } | null)?.name ?? "");
    fire(u, "onstart", { charIndex: 0 });
    fire(u, "onboundary", { charIndex: 0, name: "word" });
    scheduleEnd(chunkMs);
  };

  function playNext(): void {
    if (current || paused || pendingQueue.length === 0) return;
    const u = pendingQueue.shift() as FakeUtterance;
    current = u;
    currentStarted = false;
    // Engines start asynchronously, never synchronously inside speak().
    setTimeout(() => startCurrent(u), 15);
  }

  const synth = {
    get speaking() {
      return profile === "hung-speechd" ? hungSpeaking : current !== null;
    },
    get pending() {
      return profile === "hung-speechd"
        ? hungSpeaking
        : pendingQueue.length > 0;
    },
    get paused() {
      return paused;
    },
    onvoiceschanged: null as AnyFn | null,
    getVoices: () => voices,
    speak(u: FakeUtterance) {
      log.queued.push(u.text);
      if (profile === "hung-speechd") {
        // speech-dispatcher accepted the request but never plays it.
        hungSpeaking = true;
        return;
      }
      if (
        profile === "ios-webkit-drops-queue" &&
        (current !== null || pendingQueue.length > 0)
      ) {
        // WebKit: later queued utterances vanish without any event.
        log.dropped.push(u.text);
        return;
      }
      pendingQueue.push(u);
      playNext();
    },
    cancel() {
      log.cancelCount += 1;
      const u = current;
      clearTimer();
      current = null;
      currentStarted = false;
      pendingQueue.length = 0;
      hungSpeaking = false;
      paused = false;
      if (u && profile === "cancel-fires-end") {
        // Chrome fires the end of the cancelled utterance synchronously, inside cancel().
        fire(u, "onend", { charIndex: 0, elapsedTime: 0 });
      }
    },
    pause() {
      log.pauseCount += 1;
      if (paused) return;
      paused = true;
      if (current && timer !== null) {
        clearTimer();
        remainingMs = Math.max(0, remainingMs - (Date.now() - timerStartedAt));
        fire(current, "onpause", {});
      }
    },
    resume() {
      log.resumeCount += 1;
      if (!paused) return;
      paused = false;
      if (current) {
        fire(current, "onresume", {});
        // Continue the same utterance where it stopped: no second onstart.
        if (!currentStarted) {
          const u = current;
          setTimeout(() => startCurrent(u), 15);
        } else if (timer === null) {
          scheduleEnd(remainingMs);
        }
      } else {
        playNext();
      }
    },
    addEventListener: target.addEventListener.bind(target),
    removeEventListener: target.removeEventListener.bind(target),
    dispatchEvent: target.dispatchEvent.bind(target),
  };

  Object.defineProperty(window, "speechSynthesis", {
    value: synth,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(window, "SpeechSynthesisUtterance", {
    value: FakeUtterance,
    configurable: true,
    writable: true,
  });

  if (profile === "chrome-late-voices") {
    setTimeout(() => {
      voices = LOCAL_VOICES;
      const ev = new Event("voiceschanged");
      if (typeof synth.onvoiceschanged === "function") {
        synth.onvoiceschanged(ev);
      }
      target.dispatchEvent(ev);
    }, lateVoicesMs);
  }
}
