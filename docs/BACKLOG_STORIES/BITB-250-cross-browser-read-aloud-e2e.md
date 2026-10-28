# BITB-250: Cross-Browser Read-Aloud E2E Tests with Browser-Quirk Engine Profiles (Web)

**Status:** 🚧 In Progress (scope confirmed 2026-10-28)
**Priority:** P2
**Size:** M
**Created:** 2026-10-28
**Prompted by:** owner request 2026-10-27, after Edge and Chrome (non-Snap) were confirmed working: "Can we add
some tests to catch such issues for the major browsers?"

## Problem

Three read-aloud regressions reached production, and none was caught by the jsdom unit tests:

- BITB-241/248: a hung speech-dispatcher on Snap Firefox left the button stuck on Pause.
- BITB-249: iPhone WebKit dropped queued chunks.
- BITB-210: the button was hidden silently when the browser had only online voices.

The only Playwright project today is Chromium (`frontend/playwright.config.ts`). It has no read-aloud spec,
and no workflow runs the e2e suite on pull requests (`prod-browser-smoke.yml` only smoke-tests production).

## Decision (2026-10-28)

**Engine + quirk tests:**

- Playwright runs on **Chromium (Chrome/Edge), Firefox and WebKit (Safari and every iPhone browser)** on
  every PR.
- The app is driven through its real UI, with the backend mocked by `page.route`.
- A test `speechSynthesis` is injected with `addInitScript` and replays each known browser behaviour.
- No real-device service for now.

## Functional requirements

1. **Fake engine** (`frontend/e2e/support/fakeSpeech.ts`), installed with `page.addInitScript` and
   replacing `window.speechSynthesis` and `SpeechSynthesisUtterance`. It records every utterance
   spoken, and in what order, so a test can read them back. **Profiles**, selected per test:
   - `well-behaved`: fires `onstart`, `onboundary` and `onend` with realistic timing; voices are local.
   - `ios-webkit-drops-queue` (BITB-249): only the first utterance queued while another is pending is
     spoken; later queued ones are silently dropped.
   - `hung-speechd` (BITB-248): `speaking` and `pending` turn true immediately; no event ever fires.
   - `chrome-late-voices`: `getVoices()` is empty until `voiceschanged` fires after a delay.
   - `cancel-fires-end`: `cancel()` synchronously fires `onend`/`onerror` on the current utterance, as
     Chrome does.
   - `online-only` (BITB-210): only `localService: false` voices.
   - `no-voices`: an empty voice list.
2. **Spec** (`frontend/e2e/read-aloud.spec.ts`):
   - **Setup:** mock the chat API so an answer with several sentences, more than one chunk, renders.
     Use the same request and stream shapes the app uses; check `src/lib/api`.
   - **Assertions per profile:**
     - well-behaved, iOS profile, late voices, cancel-fires-end: every chunk is spoken, in order, and
       the button returns to Listen.
     - Pause/resume mid-answer continues without repeating or skipping a chunk.
     - hung-speechd: within about 10 s the button is Listen again and the "speech engine didn't
       respond" notice is visible. It is never stuck on Pause.
     - online-only: the consent dialog appears; Allow speaks.
     - no-voices: no Listen button, and the menu note is visible.
   - Runs at a phone viewport too, for the sticky rail.
3. **Config:** add `firefox` and `webkit` projects (and `Mobile Safari` = `devices["iPhone 13"]` on WebKit)
   to `frontend/playwright.config.ts`. Existing specs either stay Chromium-only through project-level
   `testMatch`/`grep`, or are verified to pass on the new engines. Don't break `prod-browser-smoke.yml`.
4. **CI:** a new job (or workflow) on pull requests that touch `frontend/**`:
   - Build the app.
   - Start it with `next start` via Playwright's `webServer`. Enabling it only under CI is fine, since
     the config notes a local Node issue.
   - Install the browsers with `npx playwright install --with-deps chromium firefox webkit`.
   - Run the read-aloud spec on all projects, and upload the HTML report on failure.
   - Keep it under ~10 minutes. It is not required at first, but should become required once stable.
5. **Docs:** a short README note in `frontend/e2e/` explaining how to run it locally and how to add a
   profile when a new browser quirk is found.

## Acceptance criteria

- [ ] The fake engine and its profiles, with each profile reproducing its documented bug. Proof: the
      spec fails if the BITB-248 fix or the BITB-249 sequential speaking is reverted (verify locally on
      Chromium by temporarily reverting, then restore)
- [ ] The spec passes on Chromium locally; Firefox and WebKit pass in CI
- [ ] A CI job runs on frontend PRs and uploads the report on failure
- [ ] README note on adding profiles

## Out of scope

- Real devices (BrowserStack/Sauce) and real voice output
- Android app (covered by the Robolectric/instrumented tiers)
