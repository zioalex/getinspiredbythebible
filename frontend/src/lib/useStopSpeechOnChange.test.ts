import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useStopSpeechOnChange } from "./useStopSpeechOnChange";
import { speak, getSpeakingId } from "./speech";
import {
  FakeSynth,
  installSpeechMock,
  makeVoice,
  removeSpeechMock,
} from "@/test/speechMock";

let synth: FakeSynth;

beforeEach(() => {
  synth = installSpeechMock([makeVoice("en-US")]);
});

afterEach(() => {
  removeSpeechMock();
});

describe("useStopSpeechOnChange", () => {
  it("cancels speech when the key changes, not on unrelated rerenders", () => {
    const { rerender } = renderHook(({ k }) => useStopSpeechOnChange(k), {
      initialProps: { k: "conv-1" },
    });
    speak("m1", ["Hello there."], synth.voices[0], "en");
    expect(getSpeakingId()).toBe("m1");
    synth.cancel.mockClear();

    rerender({ k: "conv-1" });
    expect(getSpeakingId()).toBe("m1");
    expect(synth.cancel).not.toHaveBeenCalled();

    rerender({ k: "conv-2" });
    expect(synth.cancel).toHaveBeenCalled();
    expect(getSpeakingId()).toBeNull();
  });
});
