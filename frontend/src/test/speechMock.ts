/**
 * Test double for the Web Speech synthesis API (BITB-119).
 * jsdom has neither `speechSynthesis` nor `SpeechSynthesisUtterance`.
 */
import { vi } from "vitest";

export interface FakeVoice {
  name: string;
  lang: string;
  localService: boolean;
  default: boolean;
  voiceURI: string;
}

export function makeVoice(
  lang: string,
  opts: Partial<FakeVoice> = {},
): FakeVoice {
  return {
    name: `voice-${lang}`,
    lang,
    localService: true,
    default: false,
    voiceURI: `voice-${lang}`,
    ...opts,
  };
}

export class FakeUtterance {
  text: string;
  voice: FakeVoice | null = null;
  lang = "";
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onstart: (() => void) | null = null;
  onresume: (() => void) | null = null;
  onboundary: (() => void) | null = null;
  constructor(text: string) {
    this.text = text;
  }
}

export interface FakeSynth {
  spoken: FakeUtterance[];
  voices: FakeVoice[];
  getVoices: ReturnType<typeof vi.fn>;
  speak: ReturnType<typeof vi.fn>;
  cancel: ReturnType<typeof vi.fn>;
  pause: ReturnType<typeof vi.fn>;
  resume: ReturnType<typeof vi.fn>;
  /** Mirrors `speechSynthesis.paused`. */
  paused: boolean;
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
  emitVoicesChanged: () => void;
}

/** Install fake speechSynthesis globals; returns the synth for assertions. */
export function installSpeechMock(voices: FakeVoice[]): FakeSynth {
  const listeners = new Set<() => void>();
  const synth: FakeSynth = {
    spoken: [],
    voices,
    getVoices: vi.fn(() => synth.voices),
    speak: vi.fn((u: FakeUtterance) => {
      synth.spoken.push(u);
    }),
    cancel: vi.fn(),
    paused: false,
    pause: vi.fn(() => {
      synth.paused = true;
    }),
    resume: vi.fn(() => {
      synth.paused = false;
    }),
    addEventListener: vi.fn((_: string, l: () => void) => {
      listeners.add(l);
    }),
    removeEventListener: vi.fn((_: string, l: () => void) => {
      listeners.delete(l);
    }),
    emitVoicesChanged: () => [...listeners].forEach((l) => l()),
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
  return synth;
}

export function removeSpeechMock(): void {
  // @ts-expect-error test cleanup of an installed global
  delete window.speechSynthesis;
  // @ts-expect-error test cleanup of an installed global
  delete window.SpeechSynthesisUtterance;
}
