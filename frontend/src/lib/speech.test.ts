import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  findLocalVoice,
  findOnlineVoice,
  getPausedId,
  getSpeakingId,
  isSpeechSupported,
  loadVoices,
  pause,
  clearStartFailed,
  getStartFailedId,
  RESUME_WATCHDOG_MS,
  START_WATCHDOG_MS,
  resume,
  speak,
  stop,
  subscribe,
  voiceAvailability,
} from "./speech";
import {
  FakeSynth,
  FakeUtterance,
  installSpeechMock,
  makeVoice,
  removeSpeechMock,
} from "@/test/speechMock";

let synth: FakeSynth;

beforeEach(() => {
  synth = installSpeechMock([]);
});

afterEach(() => {
  stop();
  removeSpeechMock();
  vi.useRealTimers();
});

describe("isSpeechSupported", () => {
  it("is false without speechSynthesis", () => {
    removeSpeechMock();
    expect(isSpeechSupported()).toBe(false);
    expect(findLocalVoice("en")).toBeNull();
  });
});

describe("findLocalVoice (local-only)", () => {
  it("ignores remote (network) voices", () => {
    synth.voices = [makeVoice("en-US", { localService: false })];
    expect(findLocalVoice("en")).toBeNull();
  });

  it("matches by primary language subtag", () => {
    synth.voices = [makeVoice("fr-FR"), makeVoice("en-GB")];
    expect(findLocalVoice("en")?.lang).toBe("en-GB");
  });

  it("prefers an exact tag match, then the default voice", () => {
    synth.voices = [
      makeVoice("pt-PT"),
      makeVoice("pt-BR", { default: true }),
      makeVoice("pt"),
    ];
    expect(findLocalVoice("pt")?.lang).toBe("pt");
    synth.voices = [makeVoice("zh-TW"), makeVoice("zh-CN", { default: true })];
    expect(findLocalVoice("zh")?.lang).toBe("zh-CN");
  });

  it("prefers the regional default before other same-language voices", () => {
    synth.voices = [
      makeVoice("zh-HK"),
      makeVoice("zh-TW", { default: true }),
      makeVoice("zh-CN"),
    ];
    expect(findLocalVoice("zh")?.lang).toBe("zh-CN");
    synth.voices = [makeVoice("pt-PT", { default: true }), makeVoice("pt-BR")];
    expect(findLocalVoice("pt")?.lang).toBe("pt-BR");
    synth.voices = [makeVoice("en-GB", { default: true }), makeVoice("en-US")];
    expect(findLocalVoice("en")?.lang).toBe("en-US");
  });

  it("falls back to default then first when no regional default is installed", () => {
    synth.voices = [makeVoice("zh-HK"), makeVoice("zh-TW", { default: true })];
    expect(findLocalVoice("zh")?.lang).toBe("zh-TW");
    synth.voices = [makeVoice("zh-HK"), makeVoice("zh-TW")];
    expect(findLocalVoice("zh")?.lang).toBe("zh-HK");
  });

  it("handles underscore language tags (Android-style)", () => {
    synth.voices = [makeVoice("ko_KR")];
    expect(findLocalVoice("ko")?.lang).toBe("ko_KR");
  });

  it.each(["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"])(
    "finds a local %s voice and nothing for other languages",
    (lang) => {
      synth.voices = [makeVoice(`${lang}-XX`)];
      expect(findLocalVoice(lang)?.lang).toBe(`${lang}-XX`);
      expect(findLocalVoice(lang === "en" ? "de" : "en")).toBeNull();
    },
  );
});

describe("loadVoices", () => {
  it("resolves immediately when voices are already present", async () => {
    synth.voices = [makeVoice("en-US")];
    await expect(loadVoices()).resolves.toBeUndefined();
    expect(synth.addEventListener).not.toHaveBeenCalled();
  });

  it("waits for voiceschanged", async () => {
    let resolved = false;
    const p = loadVoices().then(() => {
      resolved = true;
    });
    await Promise.resolve();
    expect(resolved).toBe(false);
    synth.voices = [makeVoice("en-US")];
    synth.emitVoicesChanged();
    await p;
    expect(resolved).toBe(true);
  });

  it("gives up after the timeout", async () => {
    vi.useFakeTimers();
    const p = loadVoices(100);
    await vi.advanceTimersByTimeAsync(150);
    await expect(p).resolves.toBeUndefined();
  });
});

describe("speak / stop", () => {
  const voice = makeVoice("en-US") as unknown as SpeechSynthesisVoice;

  it("queues one utterance per chunk in order, without cancelling an idle engine", () => {
    speak("m1", ["one", "two", "three"], voice, "en");
    expect(synth.cancel).not.toHaveBeenCalled();
    expect(synth.spoken.map((u) => u.text)).toEqual(["one", "two", "three"]);
    expect(synth.spoken.every((u) => u.voice === (voice as unknown))).toBe(
      true,
    );
    expect(synth.spoken[0].lang).toBe("en-US");
    expect(getSpeakingId()).toBe("m1");
  });

  it("clears the speaking id when the last chunk ends", () => {
    speak("m1", ["one", "two"], voice, "en");
    synth.spoken[0].onend?.(); // only the last utterance finishes the answer
    expect(getSpeakingId()).toBe("m1");
    synth.spoken[1].onend?.();
    expect(getSpeakingId()).toBeNull();
  });

  it("stops and drops the queue when a chunk errors", () => {
    speak("m1", ["one", "two"], voice, "en");
    synth.spoken[0].onstart?.();
    synth.cancel.mockClear();
    synth.spoken[0].onerror?.();
    expect(getSpeakingId()).toBeNull();
    expect(synth.cancel).toHaveBeenCalled();
  });

  it("stop() cancels and clears", () => {
    speak("m1", ["one"], voice, "en");
    stop();
    expect(getSpeakingId()).toBeNull();
    expect(synth.cancel).toHaveBeenCalledTimes(1); // our reading was active
    synth.cancel.mockClear();
    stop(); // idle: nothing to cancel
    expect(synth.cancel).not.toHaveBeenCalled();
  });

  it("one voice at a time: a second speak() replaces the first", () => {
    speak("m1", ["a"], voice, "en");
    const first = synth.spoken[0];
    expect(synth.cancel).not.toHaveBeenCalled();
    speak("m2", ["b"], voice, "en"); // engine flags stay false: switching must still cancel
    expect(synth.cancel).toHaveBeenCalledTimes(1);
    expect(getSpeakingId()).toBe("m2");
    // The first message's late end/error events must not clobber the new speaker.
    first.onend?.();
    first.onerror?.();
    expect(getSpeakingId()).toBe("m2");
  });

  it("ignores empty chunk lists", () => {
    speak("m1", [], voice, "en");
    expect(getSpeakingId()).toBeNull();
    expect(synth.speak).not.toHaveBeenCalled();
  });

  it("notifies subscribers on change and stops notifying after unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    speak("m1", ["a"], voice, "en");
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    stop();
    expect(listener).toHaveBeenCalledTimes(1);
  });
});

describe("pause / resume (BITB-205)", () => {
  const voice = makeVoice("en-US") as unknown as SpeechSynthesisVoice;
  const chunks = ["one", "two", "three"];
  const originalUA = navigator.userAgent;

  const setUserAgent = (ua: string) =>
    Object.defineProperty(navigator, "userAgent", {
      value: ua,
      configurable: true,
    });

  afterEach(() => setUserAgent(originalUA));

  /** Simulate the browser starting chunk `i` of the current queue. */
  const startChunk = (i: number, queue: FakeUtterance[] = synth.spoken) =>
    queue.find((u) => u.text === chunks[i])?.onstart?.();

  it("native path: pause() calls synth.pause, keeps the position and flips state", () => {
    speak("m1", chunks, voice, "en");
    pause();
    expect(synth.pause).toHaveBeenCalledTimes(1);
    expect(synth.cancel).not.toHaveBeenCalled(); // pause never cancels natively
    expect(getSpeakingId()).toBeNull();
    expect(getPausedId()).toBe("m1");
  });

  it("native path: resume() calls synth.resume without re-queuing", () => {
    speak("m1", chunks, voice, "en");
    pause();
    expect(resume()).toBe(true);
    expect(synth.resume).toHaveBeenCalledTimes(1);
    expect(synth.spoken).toHaveLength(3);
    expect(getSpeakingId()).toBe("m1");
    expect(getPausedId()).toBeNull();
  });

  it("native path: a resume that produces events keeps the native queue (watchdog cleared)", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    pause();
    resume();
    synth.spoken[0].onresume?.();
    vi.advanceTimersByTime(RESUME_WATCHDOG_MS * 3);
    expect(synth.spoken).toHaveLength(3);
    expect(synth.cancel).not.toHaveBeenCalled();
  });

  it("native path: onboundary and onstart also count as resume progress", () => {
    vi.useFakeTimers();
    for (const signal of ["onboundary", "onstart"] as const) {
      speak("m1", chunks, voice, "en");
      const first = synth.spoken[synth.spoken.length - 3];
      pause();
      resume();
      first[signal]?.();
      const queued = synth.spoken.length;
      vi.advanceTimersByTime(RESUME_WATCHDOG_MS * 2);
      expect(synth.spoken).toHaveLength(queued); // no watchdog re-queue
      expect(getSpeakingId()).toBe("m1");
    }
  });

  it("watchdog: a silent native resume restarts from the chunk that was playing", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    startChunk(1); // "two" is playing
    pause();
    resume();
    synth.spoken.length = 0;
    vi.advanceTimersByTime(RESUME_WATCHDOG_MS);
    expect(synth.spoken.map((u) => u.text)).toEqual(["two", "three"]);
    expect(getSpeakingId()).toBe("m1");
    expect(getPausedId()).toBeNull();
  });

  it("watchdog fallback un-pauses an engine whose native resume was a no-op", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    startChunk(1);
    pause();
    synth.resume.mockImplementation(() => {}); // Chrome: resume() silently does nothing
    resume();
    expect(synth.paused).toBe(true);
    synth.spoken.length = 0;
    synth.resume.mockClear();
    vi.advanceTimersByTime(RESUME_WATCHDOG_MS);
    expect(synth.resume).toHaveBeenCalled(); // engine un-paused before re-speaking
    expect(synth.spoken.map((u) => u.text)).toEqual(["two", "three"]);
  });

  it("watchdog does not fire when stopped or paused again before it elapses", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    pause();
    resume();
    pause();
    synth.spoken.length = 0;
    vi.advanceTimersByTime(RESUME_WATCHDOG_MS * 2);
    expect(synth.spoken).toHaveLength(0);
    expect(getPausedId()).toBe("m1");
  });

  it("Android UA: pause cancels the queue and resume re-speaks from the playing chunk", () => {
    setUserAgent("Mozilla/5.0 (Linux; Android 14) Chrome/120 Mobile Safari");
    speak("m1", chunks, voice, "en");
    startChunk(1);
    pause();
    expect(synth.pause).not.toHaveBeenCalled();
    expect(synth.cancel).toHaveBeenCalledTimes(1); // the pause fallback's cancel
    expect(getPausedId()).toBe("m1");

    synth.spoken.length = 0;
    expect(resume()).toBe(true);
    expect(synth.resume).not.toHaveBeenCalled();
    expect(synth.spoken.map((u) => u.text)).toEqual(["two", "three"]);
    expect(getSpeakingId()).toBe("m1");
  });

  it("Android UA: callbacks from the cancelled queue are ignored", () => {
    setUserAgent("Mozilla/5.0 (Linux; Android 14) Chrome/120");
    speak("m1", chunks, voice, "en");
    const stale = synth.spoken[synth.spoken.length - 1];
    pause();
    stale.onend?.();
    stale.onerror?.();
    expect(getPausedId()).toBe("m1");
  });

  it("finishing the last chunk after a resume clears everything", () => {
    speak("m1", chunks, voice, "en");
    pause();
    resume();
    synth.spoken[2].onend?.();
    expect(getSpeakingId()).toBeNull();
    expect(getPausedId()).toBeNull();
    expect(resume()).toBe(false);
  });

  it("speak() of another id discards the paused position", () => {
    speak("m1", chunks, voice, "en");
    pause();
    speak("m2", ["x"], voice, "en");
    expect(getPausedId()).toBeNull();
    expect(getSpeakingId()).toBe("m2");
    // a natively paused queue is un-paused so the new speech is audible
    expect(synth.resume).toHaveBeenCalled();
  });

  it("stop() while paused clears the position and resume() then does nothing", () => {
    speak("m1", chunks, voice, "en");
    pause();
    stop();
    expect(getPausedId()).toBeNull();
    expect(getSpeakingId()).toBeNull();
    expect(resume()).toBe(false);
  });

  it("pause() with nothing speaking is a no-op", () => {
    pause();
    expect(synth.pause).not.toHaveBeenCalled();
    expect(getPausedId()).toBeNull();
  });

  it("notifies subscribers on pause and resume", () => {
    const listener = vi.fn();
    speak("m1", chunks, voice, "en");
    const unsubscribe = subscribe(listener);
    pause();
    resume();
    expect(listener).toHaveBeenCalledTimes(2);
    unsubscribe();
  });
});

// BITB-210
describe("online voices and availability", () => {
  const online = (lang: string, extra = {}) =>
    makeVoice(lang, { localService: false, name: `online-${lang}`, ...extra });

  it("findOnlineVoice ignores local voices and other languages", () => {
    synth.voices = [makeVoice("en-US"), online("de-DE")];
    expect(findOnlineVoice("en")).toBeNull();
    expect(findOnlineVoice("de")?.name).toBe("online-de-DE");
  });

  it("ranks online voices: exact tag, regional default, default, first", () => {
    synth.voices = [online("zh-TW"), online("zh-CN"), online("zh-HK")];
    expect(findOnlineVoice("zh")?.lang).toBe("zh-CN");
    synth.voices = [online("zh-HK"), online("zh-TW", { default: true })];
    expect(findOnlineVoice("zh")?.lang).toBe("zh-TW");
    synth.voices = [online("zh-HK"), online("zh-TW")];
    expect(findOnlineVoice("zh")?.lang).toBe("zh-HK");
    synth.voices = [online("en-GB"), online("en-US")];
    expect(findOnlineVoice("en-GB")?.lang).toBe("en-GB");
  });

  it("voiceAvailability: local wins, then online, then none", () => {
    synth.voices = [online("en-US"), makeVoice("en-GB")];
    expect(voiceAvailability("en")).toBe("local");
    synth.voices = [online("en-US")];
    expect(voiceAvailability("en")).toBe("online");
    synth.voices = [makeVoice("de-DE")];
    expect(voiceAvailability("en")).toBe("none");
    removeSpeechMock();
    expect(voiceAvailability("en")).toBe("none");
    expect(findOnlineVoice("en")).toBeNull();
  });

  it("speak() uses an online voice unchanged", () => {
    const v = online("en-US") as unknown as SpeechSynthesisVoice;
    speak("m1", ["Hello"], v, "en");
    expect(synth.spoken[0].voice).toBe(v);
    expect(getSpeakingId()).toBe("m1");
  });
});

describe("start watchdog (BITB-238)", () => {
  const voice = makeVoice("en-US") as unknown as SpeechSynthesisVoice;
  const chunks = ["one", "two"];

  it("does not cancel an idle engine before speaking", () => {
    speak("m1", chunks, voice, "en");
    expect(synth.cancel).not.toHaveBeenCalled();
  });

  it.each([
    ["speaking", { speaking: true }],
    ["pending", { pending: true }],
    ["paused", { paused: true }],
  ] as const)("still cancels first when the engine is %s", (_, flags) => {
    Object.assign(synth, flags);
    speak("m1", chunks, voice, "en");
    expect(synth.cancel).toHaveBeenCalledTimes(1);
    if (flags.paused) expect(synth.resume).toHaveBeenCalled(); // BITB-205 rule
  });

  it("a natively paused queue is cancelled and resumed when another answer is spoken", () => {
    speak("m1", chunks, voice, "en");
    pause();
    synth.cancel.mockClear();
    speak("m2", ["x"], voice, "en");
    expect(synth.cancel).toHaveBeenCalledTimes(1);
    expect(synth.paused).toBe(false);
    expect(getPausedId()).toBeNull();
    expect(getSpeakingId()).toBe("m2");
  });

  it("silent engine: one retry, then idle and a start failure is recorded", () => {
    vi.useFakeTimers();
    const listener = vi.fn();
    subscribe(listener);
    speak("m1", chunks, voice, "en");
    expect(getSpeakingId()).toBe("m1");
    vi.advanceTimersByTime(START_WATCHDOG_MS);
    expect(synth.spoken).toHaveLength(4); // re-queued from the same chunk
    expect(synth.spoken.slice(2).map((u) => u.text)).toEqual(chunks);
    expect(synth.cancel).not.toHaveBeenCalled(); // idle engine: nothing to cancel
    expect(getSpeakingId()).toBe("m1");
    expect(getStartFailedId()).toBeNull();
    vi.advanceTimersByTime(START_WATCHDOG_MS);
    expect(getSpeakingId()).toBeNull();
    expect(getPausedId()).toBeNull();
    expect(getStartFailedId()).toBe("m1");
    expect(listener).toHaveBeenCalled();
    vi.advanceTimersByTime(START_WATCHDOG_MS * 5);
    expect(synth.spoken).toHaveLength(4); // no third attempt
  });

  it("retry cancels a stuck queue when the engine reports busy", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    synth.pending = true;
    vi.advanceTimersByTime(START_WATCHDOG_MS);
    expect(synth.cancel).toHaveBeenCalledTimes(1);
  });

  it("starts on the retry: plays normally and records no failure", () => {
    vi.useFakeTimers();
    synth.speakHook = (u, nth) => {
      if (nth === 3) setTimeout(() => u.onstart?.(), 10); // first chunk of attempt 2
    };
    speak("m1", chunks, voice, "en");
    vi.advanceTimersByTime(START_WATCHDOG_MS + 10);
    vi.advanceTimersByTime(START_WATCHDOG_MS * 3);
    expect(synth.spoken).toHaveLength(4);
    expect(getSpeakingId()).toBe("m1");
    expect(getStartFailedId()).toBeNull();
    synth.lastQueue(2)[1].onend?.();
    expect(getSpeakingId()).toBeNull();
  });

  it("onstart or onboundary of the first attempt cancels the watchdog", () => {
    vi.useFakeTimers();
    for (const signal of ["onstart", "onboundary"] as const) {
      speak("m1", chunks, voice, "en");
      synth.lastQueue(2)[0][signal]?.();
      const queued = synth.spoken.length;
      vi.advanceTimersByTime(START_WATCHDOG_MS * 3);
      expect(synth.spoken).toHaveLength(queued);
      expect(getSpeakingId()).toBe("m1");
      expect(getStartFailedId()).toBeNull();
      stop();
    }
  });

  it("a first-chunk error before any start gives up without a retry", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    synth.speaking = true;
    synth.lastQueue(2)[0].onerror?.();
    expect(getSpeakingId()).toBeNull();
    expect(getStartFailedId()).toBe("m1");
    expect(synth.cancel).toHaveBeenCalled(); // drops the rest of the queue
    vi.advanceTimersByTime(START_WATCHDOG_MS * 3);
    expect(synth.spoken).toHaveLength(2);
  });

  it("an error after the reading started is a normal finish, not a failure", () => {
    speak("m1", chunks, voice, "en");
    synth.lastQueue(2)[0].onstart?.();
    synth.lastQueue(2)[0].onerror?.();
    expect(getSpeakingId()).toBeNull();
    expect(getStartFailedId()).toBeNull();
  });

  it("the failure clears on the next speak() and on stop()", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    vi.advanceTimersByTime(START_WATCHDOG_MS * 2);
    expect(getStartFailedId()).toBe("m1");
    speak("m1", chunks, voice, "en");
    expect(getStartFailedId()).toBeNull();
    vi.advanceTimersByTime(START_WATCHDOG_MS * 2);
    expect(getStartFailedId()).toBe("m1");
    stop();
    expect(getStartFailedId()).toBeNull();
    speak("m1", chunks, voice, "en");
    vi.advanceTimersByTime(START_WATCHDOG_MS * 2);
    clearStartFailed();
    expect(getStartFailedId()).toBeNull();
  });

  it("stop() and pause() disarm the start watchdog; a second speak() supersedes the first", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    stop();
    vi.advanceTimersByTime(START_WATCHDOG_MS * 3);
    expect(getStartFailedId()).toBeNull();
    expect(synth.spoken).toHaveLength(2);

    speak("m1", chunks, voice, "en");
    pause();
    vi.advanceTimersByTime(START_WATCHDOG_MS * 3);
    expect(getPausedId()).toBe("m1");
    expect(getStartFailedId()).toBeNull();
    stop();

    speak("m1", chunks, voice, "en");
    vi.advanceTimersByTime(START_WATCHDOG_MS - 100);
    speak("m2", ["z"], voice, "en");
    vi.advanceTimersByTime(START_WATCHDOG_MS - 100); // m1's old timer must not fire
    expect(getSpeakingId()).toBe("m2");
    expect(getStartFailedId()).toBeNull();
  });

  it("the resume watchdog and the start watchdog do not clear each other", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    synth.lastQueue(2)[0].onstart?.(); // start watchdog satisfied
    pause();
    resume();
    synth.spoken.length = 0;
    vi.advanceTimersByTime(RESUME_WATCHDOG_MS); // resume watchdog restarts the queue
    expect(synth.spoken.map((u) => u.text)).toEqual(chunks);
    // ...which arms a fresh start watchdog that gives up if that restart is silent too.
    vi.advanceTimersByTime(START_WATCHDOG_MS * 2);
    expect(getStartFailedId()).toBe("m1");
  });

  it("engine reporting speaking=true at timeout counts as started (no retry, no failure)", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    synth.speaking = true; // never fired onstart/onboundary
    vi.advanceTimersByTime(START_WATCHDOG_MS * 3);
    expect(synth.spoken).toHaveLength(2);
    expect(getSpeakingId()).toBe("m1");
    expect(getStartFailedId()).toBeNull();
  });

  it("a non-final chunk's onend counts as a start signal", () => {
    vi.useFakeTimers();
    speak("m1", chunks, voice, "en");
    synth.lastQueue(2)[0].onend?.();
    vi.advanceTimersByTime(START_WATCHDOG_MS * 3);
    expect(synth.spoken).toHaveLength(2);
    expect(getSpeakingId()).toBe("m1");
    expect(getStartFailedId()).toBeNull();
  });
});
