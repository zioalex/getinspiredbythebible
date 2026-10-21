import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  findLocalVoice,
  getSpeakingId,
  isSpeechSupported,
  loadVoices,
  speak,
  stop,
  subscribe,
} from "./speech";
import {
  FakeSynth,
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

  it("cancels first, then queues one utterance per chunk in order", () => {
    speak("m1", ["one", "two", "three"], voice, "en");
    expect(synth.cancel).toHaveBeenCalledTimes(1);
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
    synth.cancel.mockClear();
    synth.spoken[0].onerror?.();
    expect(getSpeakingId()).toBeNull();
    expect(synth.cancel).toHaveBeenCalled();
  });

  it("stop() cancels and clears", () => {
    speak("m1", ["one"], voice, "en");
    stop();
    expect(getSpeakingId()).toBeNull();
    expect(synth.cancel).toHaveBeenCalledTimes(2);
  });

  it("one voice at a time: a second speak() replaces the first", () => {
    speak("m1", ["a"], voice, "en");
    const first = synth.spoken[0];
    speak("m2", ["b"], voice, "en");
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
