import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import ListenButton from "./ListenButton";
import enMessages from "../../messages/en.json";
import itMessages from "../../messages/it.json";
import { ServerConfigProvider } from "@/lib/serverConfig";
import { __resetClientEventsForTest } from "@/lib/clientEvents";
import { setShowListen } from "@/lib/ttsPreference";
import {
  __resetOnlineVoiceConsentForTest,
  getOnlineVoiceConsent,
  setOnlineVoiceConsent,
} from "@/lib/onlineVoiceConsent";
import { getPausedId, getSpeakingId, stop } from "@/lib/speech";
import {
  FakeSynth,
  installSpeechMock,
  makeVoice,
  removeSpeechMock,
} from "@/test/speechMock";

const messagesByLocale = { en: enMessages, it: itMessages } as const;

function ui(messageId: string, content: string, locale: "en" | "it" = "en") {
  return (
    <NextIntlClientProvider locale={locale} messages={messagesByLocale[locale]}>
      <ServerConfigProvider apiUrl="http://test.example">
        <ListenButton messageId={messageId} content={content} />
      </ServerConfigProvider>
    </NextIntlClientProvider>
  );
}

let synth: FakeSynth;
let fetchMock: ReturnType<typeof vi.fn>;

function mockConfig(body: unknown, ok = true) {
  fetchMock.mockImplementation((url: string) =>
    String(url).endsWith("/config")
      ? Promise.resolve({ ok, json: async () => body })
      : Promise.resolve({ ok: true }),
  );
}

function eventPosts() {
  return fetchMock.mock.calls
    .filter((c) => String(c[0]).endsWith("/api/v1/client-events"))
    .map((c) => JSON.parse(c[1].body));
}

beforeEach(() => {
  localStorage.clear();
  __resetOnlineVoiceConsentForTest();
  __resetClientEventsForTest();
  synth = installSpeechMock([makeVoice("en-US"), makeVoice("it-IT")]);
  fetchMock = vi.fn();
  global.fetch = fetchMock as unknown as typeof fetch;
  mockConfig({ features: { tts_enabled: true } });
});

afterEach(() => {
  stop();
  removeSpeechMock();
});

const LISTEN = /listen to this answer/i;
const PAUSE = /pause reading/i;
const RESUME = /resume reading/i;

describe("ListenButton visibility", () => {
  it("shows when a local voice exists (flag on by default, fail open)", async () => {
    mockConfig({}, false); // /config unreachable
    render(ui("m1", "Peace be with you."));
    expect(await screen.findByRole("button", { name: LISTEN })).toBeVisible();
  });

  it("is hidden with no voice at all and reports tts_unavailable once", async () => {
    synth.voices = [makeVoice("de-DE", { localService: false })];
    const { container } = render(ui("m1", "Hello"));
    await waitFor(() =>
      expect(eventPosts()).toEqual([
        { event: "tts_unavailable", locale: "en" },
      ]),
    );
    expect(container.querySelector("button")).toBeNull();
    // a second button for the same locale must not re-report
    render(ui("m2", "Hello again"));
    await act(async () => {
      await Promise.resolve();
    });
    expect(eventPosts()).toHaveLength(1);
  });

  it("is hidden and reports unavailable when speechSynthesis is missing", async () => {
    removeSpeechMock();
    const { container } = render(ui("m1", "Hello"));
    await waitFor(() => expect(eventPosts()).toHaveLength(1));
    expect(container.querySelector("button")).toBeNull();
  });

  it("is hidden when no local voice matches the UI language", async () => {
    synth.voices = [makeVoice("de-DE")];
    const { container } = render(ui("m1", "Hello"));
    await waitFor(() => expect(eventPosts()).toHaveLength(1));
    expect(container.querySelector("button")).toBeNull();
  });

  it("is hidden when the server flag is explicitly false (no telemetry)", async () => {
    mockConfig({ features: { tts_enabled: false } });
    render(ui("m1", "Hello"));
    // Initially shown (fail open) until /config says otherwise.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: LISTEN })).toBeNull(),
    );
    expect(eventPosts().filter((e) => e.event === "tts_unavailable")).toEqual(
      [],
    );
  });

  it("is hidden when the user preference is off (no telemetry)", async () => {
    setShowListen(false);
    const { container } = render(ui("m1", "Hello"));
    await act(async () => {
      await Promise.resolve();
    });
    expect(container.querySelector("button")).toBeNull();
    expect(eventPosts()).toEqual([]);
  });

  it("hides live when the preference is switched off, and stops speaking", async () => {
    render(ui("m1", "Hello"));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    expect(getSpeakingId()).toBe("m1");
    act(() => setShowListen(false));
    expect(screen.queryByRole("button")).toBeNull();
    expect(getSpeakingId()).toBeNull();
  });

  it("renders nothing for empty content", async () => {
    const { container } = render(ui("m1", "  \n "));
    await act(async () => {
      await Promise.resolve();
    });
    expect(container.querySelector("button")).toBeNull();
  });
});

describe("ListenButton behaviour", () => {
  it("speaks the normalized chunks with the local voice and reports tts_started", async () => {
    render(ui("m1", "Read **John 3:16** today."));
    const button = await screen.findByRole("button", { name: LISTEN });
    expect(button).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(button);
    expect(synth.spoken.map((u) => u.text)).toEqual([
      "Read John chapter 3, verse 16 today.",
    ]);
    expect(synth.spoken[0].voice?.lang).toBe("en-US");
    expect(eventPosts()).toEqual([{ event: "tts_started", locale: "en" }]);
  });

  it("flips to Pause with aria-pressed, then Resume when paused, then back to Pause", async () => {
    render(ui("m1", "Hello there."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    const pauseButton = screen.getByRole("button", { name: PAUSE });
    expect(pauseButton).toHaveAttribute("aria-pressed", "true");
    expect(pauseButton).toHaveAttribute("data-state", "playing");

    fireEvent.click(pauseButton);
    expect(synth.pause).toHaveBeenCalled();
    expect(getPausedId()).toBe("m1");
    const resumeButton = screen.getByRole("button", { name: RESUME });
    expect(resumeButton).toHaveAttribute("aria-pressed", "false");
    expect(resumeButton).toHaveAttribute("data-state", "paused");

    fireEvent.click(resumeButton);
    expect(synth.resume).toHaveBeenCalled();
    expect(getSpeakingId()).toBe("m1");
    expect(screen.getByRole("button", { name: PAUSE })).toBeInTheDocument();
    // Pause / resume are not new "started" events.
    expect(eventPosts()).toHaveLength(1);
  });

  it("shows Listen again once a paused answer is stopped", async () => {
    render(ui("m1", "Hello there."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.click(screen.getByRole("button", { name: PAUSE }));
    act(() => stop());
    expect(screen.getByRole("button", { name: LISTEN })).toHaveAttribute(
      "data-state",
      "idle",
    );
  });

  it("reverts to Listen when the answer finishes", async () => {
    render(ui("m1", "Hello there."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    act(() => synth.spoken[synth.spoken.length - 1].onend?.());
    expect(screen.getByRole("button", { name: LISTEN })).toBeInTheDocument();
  });

  it("starting another message stops the first", async () => {
    render(
      <>
        {ui("m1", "First answer.")}
        {ui("m2", "Second answer.")}
      </>,
    );
    const buttons = await screen.findAllByRole("button", { name: LISTEN });
    fireEvent.click(buttons[0]);
    expect(getSpeakingId()).toBe("m1");
    fireEvent.click(screen.getAllByRole("button", { name: LISTEN })[0]);
    expect(getSpeakingId()).toBe("m2");
    // exactly one Pause button is showing
    expect(screen.getAllByRole("button", { name: PAUSE })).toHaveLength(1);
  });

  it("playing another message discards the first one's paused position", async () => {
    render(
      <>
        {ui("m1", "First answer.")}
        {ui("m2", "Second answer.")}
      </>,
    );
    const buttons = await screen.findAllByRole("button", { name: LISTEN });
    fireEvent.click(buttons[0]);
    fireEvent.click(screen.getByRole("button", { name: PAUSE }));
    expect(getPausedId()).toBe("m1");
    fireEvent.click(screen.getAllByRole("button", { name: LISTEN })[0]);
    expect(getSpeakingId()).toBe("m2");
    expect(getPausedId()).toBeNull();
    expect(screen.getAllByRole("button", { name: LISTEN })).toHaveLength(1);
  });

  it("unmounting a paused message clears its paused position", async () => {
    const { unmount } = render(ui("m1", "Hello there."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.click(screen.getByRole("button", { name: PAUSE }));
    unmount();
    expect(getPausedId()).toBeNull();
  });

  it("unmounting the speaking message cancels playback", async () => {
    const { unmount } = render(ui("m1", "Hello there."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    synth.cancel.mockClear();
    unmount();
    expect(synth.cancel).toHaveBeenCalled();
    expect(getSpeakingId()).toBeNull();
  });

  it("unmounting a message that is not speaking leaves another one alone", async () => {
    const a = render(ui("m1", "First."));
    render(ui("m2", "Second."));
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: LISTEN })).toHaveLength(2),
    );
    fireEvent.click(screen.getAllByRole("button", { name: LISTEN })[1]);
    a.unmount();
    expect(getSpeakingId()).toBe("m2");
  });

  it("changing the UI language stops playback and uses the localized label and voice", async () => {
    const { rerender } = render(ui("m1", "Hello there."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    expect(getSpeakingId()).toBe("m1");
    rerender(ui("m1", "Ciao a tutti.", "it"));
    expect(getSpeakingId()).toBeNull();
    const button = await screen.findByRole("button", {
      name: itMessages.Chat.listenAnswer,
    });
    fireEvent.click(button);
    expect(synth.spoken[synth.spoken.length - 1].voice?.lang).toBe("it-IT");
  });
});

// BITB-210: online-only browsers get a per-device opt-in instead of a silent miss.
describe("ListenButton online voices (BITB-210)", () => {
  const DIALOG = { name: /use an online voice/i };

  beforeEach(() => {
    synth.voices = [makeVoice("en-US", { localService: false })];
  });

  it("shows Listen for an online-only voice and opens the consent dialog first", async () => {
    render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    expect(screen.getByRole("dialog", DIALOG)).toBeVisible();
    expect(synth.speak).not.toHaveBeenCalled();
    expect(eventPosts().filter((e) => e.event === "tts_unavailable")).toEqual(
      [],
    );
  });

  it("Allow persists consent and speaks with the online voice immediately", async () => {
    render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.click(
      screen.getByRole("button", { name: /allow online voices/i }),
    );
    expect(getOnlineVoiceConsent()).toBe("granted");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(getSpeakingId()).toBe("m1");
    expect(synth.spoken[0].voice?.localService).toBe(false);
    expect(eventPosts()).toContainEqual({ event: "tts_started", locale: "en" });
    // pause / resume work like a local voice
    fireEvent.click(screen.getByRole("button", { name: PAUSE }));
    expect(getPausedId()).toBe("m1");
  });

  it("Not now persists the decision and hides the button", async () => {
    const { container } = render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.click(screen.getByRole("button", { name: /not now/i }));
    expect(getOnlineVoiceConsent()).toBe("denied");
    expect(container.querySelector("button")).toBeNull();
    expect(synth.speak).not.toHaveBeenCalled();
  });

  it("Esc counts as Not now", async () => {
    const { container } = render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(getOnlineVoiceConsent()).toBe("denied");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(container.querySelector("button")).toBeNull();
  });

  it("stays hidden when consent was already denied", async () => {
    setOnlineVoiceConsent("denied");
    const { container } = render(ui("m1", "Hello"));
    await act(async () => {
      await Promise.resolve();
    });
    expect(container.querySelector("button")).toBeNull();
  });

  it("speaks without a dialog when consent was already granted", async () => {
    setOnlineVoiceConsent("granted");
    render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(getSpeakingId()).toBe("m1");
  });

  it("prefers an offline voice over an online one even after consent", async () => {
    setOnlineVoiceConsent("granted");
    synth.voices = [
      makeVoice("en-US", { localService: false, name: "cloud" }),
      makeVoice("en-GB", { name: "offline" }),
    ];
    render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    expect(synth.spoken[0].voice?.name).toBe("offline");
  });

  it("an offline voice never shows the dialog", async () => {
    synth.voices = [
      makeVoice("en-US", { localService: false }),
      makeVoice("en-GB"),
    ];
    render(ui("m1", "Hello"));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(getSpeakingId()).toBe("m1");
  });

  it("revoking consent stops an online reading and hides Listen", async () => {
    setOnlineVoiceConsent("granted");
    const { container } = render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    expect(getSpeakingId()).toBe("m1");
    act(() => setOnlineVoiceConsent("denied"));
    expect(getSpeakingId()).toBeNull();
    expect(container.querySelector("button")).toBeNull();
  });

  it("revoking consent while paused drops the paused position", async () => {
    setOnlineVoiceConsent("granted");
    render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.click(screen.getByRole("button", { name: PAUSE }));
    expect(getPausedId()).toBe("m1");
    act(() => setOnlineVoiceConsent("denied"));
    expect(getPausedId()).toBeNull();
  });

  it("renders the dialog in a portal on document.body, outside the sticky rail", async () => {
    const { container } = render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    const dialog = screen.getByRole("dialog", DIALOG);
    expect(container.contains(dialog)).toBe(false);
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog).toHaveAttribute("aria-describedby");
    expect(
      document.getElementById(dialog.getAttribute("aria-describedby")!),
    ).toHaveTextContent(/speech service/i);
  });

  it("focuses inside the dialog and Shift+Tab from open stays inside", async () => {
    render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    const dialog = screen.getByRole("dialog", DIALOG);
    expect(dialog.contains(document.activeElement)).toBe(true);
    const notNow = screen.getByRole("button", { name: /not now/i });
    const allow = screen.getByRole("button", { name: /allow online voices/i });
    expect(document.activeElement).toBe(notNow);
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(allow);
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(notNow);
  });

  it("returns focus to the next rail control after Not now", async () => {
    render(
      <div>
        {ui("m1", "Peace be with you.")}
        <button>Share</button>
      </div>,
    );
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.click(screen.getByRole("button", { name: /not now/i }));
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: "Share" }),
      ),
    );
  });

  it("keeps the choice when localStorage is blocked", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.click(
      screen.getByRole("button", { name: /allow online voices/i }),
    );
    expect(getSpeakingId()).toBe("m1");
    // a second tap pauses instead of reopening the dialog
    fireEvent.click(screen.getByRole("button", { name: PAUSE }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(getPausedId()).toBe("m1");
    vi.restoreAllMocks();
  });

  it("Not now hides the button even when localStorage is blocked", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { container } = render(ui("m1", "Peace be with you."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    fireEvent.click(screen.getByRole("button", { name: /not now/i }));
    expect(container.querySelector("button")).toBeNull();
    vi.restoreAllMocks();
  });

  it("shows the dialog in the UI language", async () => {
    render(ui("m1", "La pace sia con te.", "it"));
    synth.voices = [makeVoice("it-IT", { localService: false })];
    act(() => synth.emitVoicesChanged());
    fireEvent.click(
      await screen.findByRole("button", { name: /ascolta la risposta/i }),
    );
    expect(
      screen.getByRole("dialog", { name: /usare una voce online/i }),
    ).toBeVisible();
  });
});
