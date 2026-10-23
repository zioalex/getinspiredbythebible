import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import MainMenu from "./MainMenu";
import { renderWithIntl } from "@/test/i18n-helpers";
import { getShowListen, setShowListen } from "@/lib/ttsPreference";
import {
  getOnlineVoiceConsent,
  setOnlineVoiceConsent,
} from "@/lib/onlineVoiceConsent";
import { getSpeakingId, speak, stop } from "@/lib/speech";
import { localeLabels } from "@/i18n/localeLabels";
import {
  FakeSynth,
  installSpeechMock,
  makeVoice,
  removeSpeechMock,
} from "@/test/speechMock";
import enMessages from "../../messages/en.json";
import itMessages from "../../messages/it.json";
import deMessages from "../../messages/de.json";
import esMessages from "../../messages/es.json";
import frMessages from "../../messages/fr.json";
import ptMessages from "../../messages/pt.json";
import arMessages from "../../messages/ar.json";
import ruMessages from "../../messages/ru.json";
import zhMessages from "../../messages/zh.json";
import hiMessages from "../../messages/hi.json";
import koMessages from "../../messages/ko.json";

const allMessages: Record<string, typeof enMessages> = {
  en: enMessages,
  it: itMessages,
  de: deMessages,
  es: esMessages,
  fr: frMessages,
  pt: ptMessages,
  ar: arMessages,
  ru: ruMessages,
  zh: zhMessages,
  hi: hiMessages,
  ko: koMessages,
};

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...rest }: { children: React.ReactNode }) => (
    <a {...rest}>{children}</a>
  ),
}));
vi.mock("@/components/LanguageSwitcher", () => ({ default: () => null }));
vi.mock("@/components/TranslationSwitcher", () => ({ default: () => null }));

function renderMenu() {
  renderWithIntl(
    <MainMenu
      onOpenHistory={() => {}}
      onOpenChurchFinder={() => {}}
      translations={[]}
      activeTranslationCode="KJV"
      onSelectTranslation={() => {}}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /menu/i }));
}

beforeEach(() => localStorage.clear());

describe("MainMenu — Show Listen button toggle (BITB-119)", () => {
  it("is on by default and exposes switch semantics", () => {
    renderMenu();
    const toggle = screen.getByRole("switch", { name: /show listen button/i });
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("toggles off and persists, then back on", () => {
    renderMenu();
    const toggle = screen.getByRole("switch", { name: /show listen button/i });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(getShowListen()).toBe(false);
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(getShowListen()).toBe(true);
  });

  it("reflects a previously stored 'off' preference", () => {
    setShowListen(false);
    renderMenu();
    expect(
      screen.getByRole("switch", { name: /show listen button/i }),
    ).toHaveAttribute("aria-checked", "false");
  });
});

// BITB-210: online-voice toggle + "no voice" note.
const LOCALES = [
  "en",
  "it",
  "de",
  "es",
  "fr",
  "pt",
  "ar",
  "ru",
  "zh",
  "hi",
  "ko",
];

function renderMenuIn(locale: string) {
  render(
    <NextIntlClientProvider locale={locale} messages={allMessages[locale]}>
      <MainMenu
        onOpenHistory={() => {}}
        onOpenChurchFinder={() => {}}
        translations={[]}
        activeTranslationCode="KJV"
        onSelectTranslation={() => {}}
      />
    </NextIntlClientProvider>,
  );
  fireEvent.click(
    screen.getByRole("button", {
      name: allMessages[locale].Chat.mainMenuLabel,
    }),
  );
}

describe("MainMenu — online voices (BITB-210)", () => {
  let synth: FakeSynth;
  beforeEach(() => {
    synth = installSpeechMock([]);
  });
  afterEach(() => {
    stop();
    removeSpeechMock();
  });

  it.each(LOCALES)(
    "shows the none-note naming the language (%s)",
    async (locale) => {
      renderMenuIn(locale);
      const note = await screen.findByRole("status", {}, { timeout: 3000 });
      expect(note).toHaveTextContent(localeLabels[locale]);
      expect(note).toHaveTextContent(
        allMessages[locale].Chat.noVoiceForLanguage.replace(
          "{language}",
          localeLabels[locale],
        ),
      );
      expect(note).toHaveAttribute("aria-live", "polite");
      expect(
        screen.queryByRole("switch", {
          name: allMessages[locale].Chat.allowOnlineVoices,
        }),
      ).toBeNull();
    },
  );

  it.each(LOCALES)(
    "shows the online toggle, not the note (%s)",
    async (locale) => {
      synth.voices = [makeVoice(locale, { localService: false })];
      renderMenuIn(locale);
      const toggle = await screen.findByRole("switch", {
        name: allMessages[locale].Chat.allowOnlineVoices,
      });
      expect(toggle).toHaveAttribute("aria-checked", "false");
      expect(screen.queryByRole("status")).toBeNull();
    },
  );

  it("hides both when only an offline voice exists", async () => {
    synth.voices = [makeVoice("en-US")];
    renderMenuIn("en");
    await screen.findByRole("switch", { name: /show listen button/i });
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByRole("status")).toBeNull();
    expect(
      screen.queryByRole("switch", { name: /allow online voices/i }),
    ).toBeNull();
  });

  it("toggles consent on and off", async () => {
    synth.voices = [makeVoice("en-US", { localService: false })];
    renderMenuIn("en");
    const toggle = await screen.findByRole("switch", {
      name: /allow online voices/i,
    });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(getOnlineVoiceConsent()).toBe("granted");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(getOnlineVoiceConsent()).toBe("denied");
  });

  it("turning it off stops online playback", async () => {
    const voice = makeVoice("en-US", { localService: false });
    synth.voices = [voice];
    setOnlineVoiceConsent("granted");
    renderMenuIn("en");
    const toggle = await screen.findByRole("switch", {
      name: /allow online voices/i,
    });
    act(() =>
      speak("m1", ["Hello"], voice as unknown as SpeechSynthesisVoice, "en"),
    );
    expect(getSpeakingId()).toBe("m1");
    fireEvent.click(toggle);
    expect(getSpeakingId()).toBeNull();
  });

  it("never touches speechSynthesis while the Listen preference is off", async () => {
    setShowListen(false);
    renderMenuIn("en");
    await act(async () => {
      await Promise.resolve();
    });
    expect(synth.getVoices).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).toBeNull();
    expect(
      screen.queryByRole("switch", { name: /allow online voices/i }),
    ).toBeNull();
  });
});
