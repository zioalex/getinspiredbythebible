/**
 * BITB-250: cross-browser read-aloud (Listen button) e2e.
 *
 * Drives the real UI on Chromium, Firefox and WebKit (desktop + Mobile Safari) with the chat
 * backend mocked via `page.route` and a fake `speechSynthesis` (e2e/support/fakeSpeech.ts)
 * replaying each known browser quirk:
 *   - BITB-248 hung speech-dispatcher (Snap Firefox): must never stick on Pause
 *   - BITB-249 WebKit/iOS dropping queued utterances: chunks must be spoken one at a time
 *   - BITB-210 online-only voices: consent dialog; no voices: explanatory menu note
 *
 * Needs a production build (`npm run build && npm start`); see e2e/README.md.
 */
import { test, expect, type Page, type Route } from "@playwright/test";
import {
  FAKE_SPEECH_PROFILES,
  getSpeechLog,
  installFakeSpeech,
  type FakeSpeechProfile,
} from "./support/fakeSpeech";

// Eight short plain sentences (no markdown, no verse references) so the answer is read back
// verbatim: speakableChunks() packs them into several chunks of <= 200 chars joined by " ".
const ANSWER = [
  "God is close to the brokenhearted and gently holds those who are weary.",
  "You do not have to carry every worry alone, because you are deeply loved.",
  "Rest is a gift, and it is good to receive it without any guilt.",
  "Hope grows slowly, like a seed that is quietly watered each morning.",
  "Kindness toward yourself is not weakness, it is a way of listening to grace.",
  "Take one small step today and trust that strength will meet you there.",
  "Peace often arrives in quiet moments when we simply stop and breathe.",
  "You are not forgotten, and tomorrow holds fresh mercy for you.",
].join(" ");

// A second, textually distinct answer so a test can tell whose chunks were spoken.
const ANSWER_2 = [
  "Wisdom begins with listening, and listening begins with a quiet heart.",
  "When the night feels long, remember that morning has never once failed to arrive.",
  "Gratitude turns small things into blessings that are easy to overlook.",
  "Bring your questions honestly, because faith is strong enough to hold them.",
  "A gentle word can lift a burden that a loud argument never could.",
  "Walk patiently, for every road has companions you have not yet met.",
].join(" ");

const LISTEN = "Listen to this answer";
const PAUSE = "Pause reading";
const RESUME = "Resume reading";
const NO_RESPONSE = "Your browser's speech engine didn't respond.";

// CI builds with NEXT_PUBLIC_API_URL=http://localhost:3000/e2e-api: same origin as the page, so
// the mock involves no CORS preflight. A default local build still calls :8000, matched too.
const API_ORIGIN =
  /^https?:\/\/(localhost|127\.0\.0\.1)(:8000\/|:3000\/e2e-api\/)/;
const API_PREFIX = /^\/e2e-api(?=\/)/;
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET,POST,OPTIONS",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    headers: CORS,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function sse(chunks: unknown[]): string {
  return (
    chunks.map((c) => `data: ${JSON.stringify(c)}\n\n`).join("") +
    "data: [DONE]\n\n"
  );
}

/** Mocks every backend call the chat page makes; the answer streams from /chat/stream. */
async function mockBackend(page: Page) {
  let turn = 0; // answer 1, then answer 2 for a second question
  await page.route(API_ORIGIN, async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") {
      return route.fulfill({ status: 204, headers: CORS });
    }
    const pathname = new URL(request.url()).pathname.replace(API_PREFIX, "");
    if (pathname === "/config") {
      return json(route, {
        chat: { max_message_length: 2000, session_max_requests: 100 },
        security: { turnstile_enabled: false },
        features: { tts_enabled: true },
      });
    }
    if (pathname.startsWith("/health")) return json(route, { status: "ok" });
    if (pathname === "/api/v1/chat/stream") {
      turn += 1;
      const content = turn === 1 ? ANSWER : ANSWER_2;
      return route.fulfill({
        status: 200,
        headers: { ...CORS, "cache-control": "no-cache" },
        contentType: "text/event-stream",
        body: sse([
          {
            type: "metadata",
            message_id: `e2e-answer-${turn}`,
            scripture_context: { verses: [] },
            provider: "mock",
            model: "mock",
          },
          { type: "content", content },
          { type: "completion", verses_cited: [], resolved_verses: [] },
        ]),
      });
    }
    if (pathname === "/api/v1/client-events") {
      return route.fulfill({ status: 204, headers: CORS });
    }
    if (pathname === "/api/v1/scripture/translations") {
      return json(route, { translations: [] });
    }
    if (pathname === "/api/v1/scripture/book-names") {
      return json(route, { localized_to_english: {}, multi_word_names: [] });
    }
    // Anything else: an empty-but-valid payload.
    return json(route, {});
  });
}

/** Opens the chat, asks a question and waits for the mocked answer to finish rendering. */
async function askQuestion(page: Page) {
  await page.goto("/en");
  const input = page.getByPlaceholder(/Share what's on your heart/i);
  await expect(input).toBeVisible();
  await input.fill("How can I find peace today?");
  const submit = page.locator('form button[type="submit"]');
  await expect(submit).toBeEnabled({ timeout: 10_000 });
  await submit.click();
  const answer = page.getByTestId("assistant-message").last();
  await expect(answer).toContainText("God is close to the brokenhearted");
  return answer;
}

/** Asks a follow-up in the already open chat; resolves once answer number `count` rendered. */
async function askFollowUp(page: Page, count: number) {
  const input = page.getByPlaceholder(/Share what's on your heart/i);
  await input.fill("And what about wisdom?");
  const submit = page.locator('form button[type="submit"]');
  await expect(submit).toBeEnabled({ timeout: 10_000 });
  await submit.click();
  await expect(page.getByTestId("assistant-message")).toHaveCount(count);
  await expect(page.getByTestId("assistant-message").last()).toContainText(
    "Wisdom begins with listening",
  );
}

/** The rail button of the n-th (0-based) answer. */
function railButtonAt(page: Page, index: number, name: string) {
  return page
    .getByTestId("message-action-rail")
    .nth(index)
    .getByRole("button", { name, exact: true });
}

function railButton(page: Page, name: string) {
  return page
    .getByTestId("message-action-rail")
    .last()
    .getByRole("button", { name, exact: true });
}

async function setup(
  page: Page,
  profile: FakeSpeechProfile,
  options?: Parameters<typeof installFakeSpeech>[2],
) {
  // The first-visit "Why Vox Quieta" intro modal would cover the page and eat clicks.
  await page.addInitScript(() => {
    try {
      localStorage.setItem("vq:aboutIntroSeen", "1");
    } catch {
      // storage blocked: nothing to seed
    }
  });
  // Surface in-page errors in the test output: CI artifacts are not always reachable.
  page.on("console", (msg) => {
    if (msg.type() === "error") console.log(`[browser console] ${msg.text()}`);
  });
  page.on("pageerror", (err) => console.log(`[page error] ${err.message}`));
  await installFakeSpeech(page, profile, options);
  await mockBackend(page);
  return askQuestion(page);
}

// The profile each test below runs under; the guard test derives coverage from these.
// Profiles whose engine plays everything it is asked to, one chunk after another.
const PLAYS_EVERYTHING: FakeSpeechProfile[] = [
  "well-behaved",
  "ios-webkit-drops-queue",
  "chrome-late-voices",
  "cancel-fires-end",
];
const PAUSE_RESUME_PROFILES: FakeSpeechProfile[] = [
  "well-behaved",
  "ios-webkit-drops-queue",
];
const HUNG: FakeSpeechProfile = "hung-speechd";
const ONLINE_ONLY: FakeSpeechProfile = "online-only";
const NO_VOICES: FakeSpeechProfile = "no-voices";
const CANCEL_SWITCH: FakeSpeechProfile = "cancel-fires-end";

test.describe("read aloud", () => {
  // The production build registers the offline-shell service worker (public/sw.js). In WebKit
  // requests then bypass page.route and hit the real server (404), so block it while mocking.
  test.use({ serviceWorkers: "block" });

  test("every profile is exercised by this spec", () => {
    // Guards against adding a profile to the fake engine and forgetting to test it. One
    // project is enough: the check does not depend on the browser.
    test.skip(
      test.info().project.name !== "chromium",
      "browser-independent check",
    );
    const covered = new Set<FakeSpeechProfile>([
      ...PLAYS_EVERYTHING,
      ...PAUSE_RESUME_PROFILES,
      HUNG,
      ONLINE_ONLY,
      NO_VOICES,
      CANCEL_SWITCH,
    ]);
    expect([...covered].sort()).toEqual([...FAKE_SPEECH_PROFILES].sort());
  });

  for (const profile of PLAYS_EVERYTHING) {
    test(`speaks every chunk in order, then returns to Listen (${profile})`, async ({
      page,
    }) => {
      await setup(page, profile);

      // chrome-late-voices: the button only appears once `voiceschanged` has fired.
      await expect(railButton(page, LISTEN)).toBeVisible({ timeout: 10_000 });
      await railButton(page, LISTEN).click();
      await expect(railButton(page, PAUSE)).toBeVisible();
      await expect(railButton(page, LISTEN)).toBeVisible({ timeout: 15_000 });

      const log = await getSpeechLog(page);
      expect(log.spoken.length).toBeGreaterThanOrEqual(3);
      // In order, nothing repeated, nothing skipped: the chunks re-assemble the answer.
      expect(log.spoken.join(" ")).toBe(ANSWER);
      expect(log.dropped).toEqual([]);
      if (profile === "ios-webkit-drops-queue") {
        // Sequential speaking: never more than one utterance in flight.
        expect(log.queued).toEqual(log.spoken);
      }
    });
  }

  for (const profile of PAUSE_RESUME_PROFILES) {
    test(`pause and resume mid-answer continues without repeating or skipping (${profile})`, async ({
      page,
    }) => {
      await setup(page, profile, { chunkMs: 500 });

      await railButton(page, LISTEN).click();
      await expect
        .poll(async () => (await getSpeechLog(page)).spoken.length)
        .toBeGreaterThanOrEqual(1);

      await railButton(page, PAUSE).click();
      await expect(railButton(page, RESUME)).toBeVisible();
      const whilePaused = (await getSpeechLog(page)).spoken.length;
      // Nothing new is spoken while paused.
      await page.waitForTimeout(1200);
      expect((await getSpeechLog(page)).spoken.length).toBe(whilePaused);

      await railButton(page, RESUME).click();
      await expect(railButton(page, LISTEN)).toBeVisible({ timeout: 20_000 });

      const log = await getSpeechLog(page);
      expect(log.spoken.join(" ")).toBe(ANSWER);
    });
  }

  test("switching answers mid-reading cancels cleanly: no stale chunk, second answer complete (cancel-fires-end)", async ({
    page,
  }) => {
    await setup(page, CANCEL_SWITCH, { chunkMs: 500 });
    await askFollowUp(page, 2);

    // Start the first answer and wait until it is mid-reading.
    await railButtonAt(page, 0, LISTEN).click();
    await expect(railButtonAt(page, 0, PAUSE)).toBeVisible();
    await expect
      .poll(async () => (await getSpeechLog(page)).spoken.length)
      .toBeGreaterThanOrEqual(1);
    const before = await getSpeechLog(page);
    expect(before.spoken.length).toBeLessThan(3); // still mid-answer
    const cancelsBefore = before.cancelWhileSpeaking;

    // Listen on the second answer: the app cancels the engine while it is speaking, and the
    // fake fires onerror synchronously inside cancel().
    await railButtonAt(page, 1, LISTEN).click();
    await expect(railButtonAt(page, 1, PAUSE)).toBeVisible();
    await expect(railButtonAt(page, 1, LISTEN)).toBeVisible({
      timeout: 20_000,
    });
    await expect(railButtonAt(page, 0, LISTEN)).toBeVisible();

    const log = await getSpeechLog(page);
    expect(log.cancelWhileSpeaking).toBeGreaterThan(cancelsBefore);

    // Everything before the switch belongs to answer 1 (a prefix, in order); everything from
    // the first answer-2 chunk on is answer 2, complete and in order: no stale chunk of
    // answer 1 sneaks in after the switch, and nothing repeats.
    const firstOfSecond = log.spoken.findIndex((c) => ANSWER_2.includes(c));
    expect(firstOfSecond).toBeGreaterThanOrEqual(1);
    const fromFirst = log.spoken.slice(0, firstOfSecond);
    expect(fromFirst.every((c) => ANSWER.includes(c))).toBe(true);
    expect(ANSWER.startsWith(fromFirst.join(" "))).toBe(true);
    expect(log.spoken.slice(firstOfSecond).join(" ")).toBe(ANSWER_2);
  });

  test("a hung speech engine ends in Listen with a notice, never stuck on Pause (hung-speechd)", async ({
    page,
  }) => {
    test.setTimeout(45_000);
    await setup(page, HUNG);

    await railButton(page, LISTEN).click();
    // Two 3 s start-watchdog windows (one retry) -> notice, well within 10 s.
    await expect(page.getByText(NO_RESPONSE)).toBeVisible({ timeout: 10_000 });
    await expect(railButton(page, LISTEN)).toBeVisible();
    await expect(railButton(page, PAUSE)).toHaveCount(0);

    const log = await getSpeechLog(page);
    expect(log.spoken).toEqual([]); // no event ever fired
    expect(log.queued.length).toBeGreaterThanOrEqual(1);
  });

  test("online-only voices ask for consent; Allow speaks with the online voice (online-only)", async ({
    page,
  }) => {
    await setup(page, ONLINE_ONLY);

    await railButton(page, LISTEN).click();
    const dialog = page.getByRole("dialog", { name: "Use an online voice?" });
    await expect(dialog).toBeVisible();
    // Nothing is sent to the speech service before the user agrees.
    expect((await getSpeechLog(page)).queued).toEqual([]);

    await dialog.getByRole("button", { name: "Allow online voices" }).click();
    await expect(dialog).toBeHidden();
    await expect(railButton(page, PAUSE)).toBeVisible();
    await expect(railButton(page, LISTEN)).toBeVisible({ timeout: 15_000 });

    const log = await getSpeechLog(page);
    expect(log.spoken.join(" ")).toBe(ANSWER);
    expect(new Set(log.spokenVoices)).toEqual(
      new Set(["Fake Online English (US)"]),
    );
  });

  test("a browser with no voices shows no Listen button and explains why in the menu (no-voices)", async ({
    page,
  }) => {
    await setup(page, NO_VOICES);

    await page.getByRole("button", { name: "Menu" }).click();
    await expect(
      page
        .getByTestId("main-menu-panel")
        .getByText("This browser has no voice for English."),
    ).toBeVisible({ timeout: 10_000 });
    // The note only shows once the voice list was read, so "no button" is final.
    await expect(page.getByTestId("message-action-rail")).toBeVisible();
    await expect(page.getByRole("button", { name: LISTEN })).toHaveCount(0);
  });

  test("the sticky rail's Listen button works at a phone viewport", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await setup(page, "well-behaved");

    const listen = railButton(page, LISTEN);
    await expect(listen).toBeVisible();
    await expect(listen).toBeInViewport();
    const box = await listen.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(390 + 1);

    await listen.click();
    await expect(railButton(page, PAUSE)).toBeVisible();
    await expect(railButton(page, LISTEN)).toBeVisible({ timeout: 15_000 });
    expect((await getSpeechLog(page)).spoken.join(" ")).toBe(ANSWER);
  });
});
