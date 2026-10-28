# Playwright e2e

## Cross-browser read-aloud spec (BITB-250)

`read-aloud.spec.ts` drives the real chat UI and Listen button on Chromium, Firefox, WebKit and
Mobile Safari (iPhone 13 on WebKit). The backend is mocked with `page.route` (no backend server
needed), and `window.speechSynthesis` is replaced by a fake engine
(`support/fakeSpeech.ts`) that replays one known browser quirk per profile:

| Profile                  | Reproduces                                                                                                                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `well-behaved`           | start/boundary/end events, local voices                                                                                                                                                   |
| `ios-webkit-drops-queue` | BITB-249 (dropped-queue half): utterances queued behind a pending one are dropped. Garbage collection of unreferenced utterances is not deterministically emulable, so it is not modelled |
| `hung-speechd`           | BITB-248: `speaking`/`pending` go true, no event ever fires, and `cancel()` does not clear them                                                                                           |
| `chrome-late-voices`     | `getVoices()` empty until a delayed `voiceschanged`                                                                                                                                       |
| `cancel-fires-end`       | `cancel()` synchronously fires `onerror` (`interrupted`/`canceled`) on the cancelled utterances                                                                                           |
| `online-only`            | BITB-210: only `localService: false` voices                                                                                                                                               |
| `no-voices`              | empty voice list                                                                                                                                                                          |

### Run it locally

The specs need a production build (`next start`); Playwright only auto-starts it in CI.

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:3000/e2e-api npm run build && npm start &   # as CI
npx playwright install chromium firefox webkit   # once
npx playwright test e2e/read-aloud.spec.ts                       # all projects
npx playwright test e2e/read-aloud.spec.ts --project=webkit      # one engine
npx playwright show-report                                       # after a failure
```

The older specs (`chat-bottom-bar`, `turnstile-ready`, ...) stay Chromium-only: the
`firefox`, `webkit` and `Mobile Safari` projects in `playwright.config.ts` only match
`read-aloud.spec.ts` (`CROSS_BROWSER_SPECS`). CI runs this spec in
`.github/workflows/frontend-e2e.yml` on every pull request touching `frontend/**`.

Build with `NEXT_PUBLIC_API_URL=http://localhost:3000/e2e-api` as CI does: the mocked API is then
same-origin, so no CORS preflight is involved. The spec blocks service workers
(`serviceWorkers: "block"`): with the production worker (`public/sw.js`) active, WebKit sends the
API calls past `page.route` to the real server. Browser console errors are printed in the test
output prefixed `[browser console]`.

### Add a profile when a new browser quirk turns up

1. In `support/fakeSpeech.ts` add the name to the `FakeSpeechProfile` union and to
   `FAKE_SPEECH_PROFILES`, then make the fake behave like the broken browser inside
   `installInPage` (it runs in the page, so keep it self-contained: no imports). Branch on
   `profile` in `speak()`, `cancel()`, `pause()`/`resume()` or the voice list. Record anything the
   test needs to assert in the `log` object (`SpeechLog`).
2. In `read-aloud.spec.ts` add a test using `setup(page, "<profile>")` that asserts the
   user-visible outcome (button state, notice, spoken chunks via `getSpeechLog`). Add the profile
   to `PLAYS_EVERYTHING` if the engine still plays the whole answer; the "every profile is
   exercised" test fails until each profile is covered.
3. Prove the test bites: temporarily revert the app fix, confirm the new test fails, restore it.
