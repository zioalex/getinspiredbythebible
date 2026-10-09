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
import { getSpeakingId, stop } from "@/lib/speech";
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
const STOP = /stop listening/i;

describe("ListenButton visibility", () => {
  it("shows when a local voice exists (flag on by default, fail open)", async () => {
    mockConfig({}, false); // /config unreachable
    render(ui("m1", "Peace be with you."));
    expect(await screen.findByRole("button", { name: LISTEN })).toBeVisible();
  });

  it("is hidden for remote-only voices and reports tts_unavailable once", async () => {
    synth.voices = [makeVoice("en-US", { localService: false })];
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

  it("flips to Stop with aria-pressed, and a second click cancels", async () => {
    render(ui("m1", "Hello there."));
    fireEvent.click(await screen.findByRole("button", { name: LISTEN }));
    const stopButton = screen.getByRole("button", { name: STOP });
    expect(stopButton).toHaveAttribute("aria-pressed", "true");
    synth.cancel.mockClear();
    fireEvent.click(stopButton);
    expect(synth.cancel).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: LISTEN })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    // Stopping is not a new "started" event.
    expect(eventPosts()).toHaveLength(1);
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
    // exactly one Stop button is showing
    expect(screen.getAllByRole("button", { name: STOP })).toHaveLength(1);
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
