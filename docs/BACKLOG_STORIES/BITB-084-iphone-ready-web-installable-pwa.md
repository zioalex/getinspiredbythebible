# BITB-084: iPhone-Ready Web — Installable PWA, Standalone Safe Areas, and an iOS Path on `/app`

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (1–2 days)
**Created:** 2026-07-29
**Part of:** the iOS delivery plan — Stage 0 of BITB-084 → BITB-085 → BITB-086 → BITB-087 → BITB-088.
This is the only stage that needs no Apple Developer account, no Mac, and no new client codebase,
and it is worth shipping **even if the native app never happens**.

## User Story

**As an** iPhone user, **I want** Vox Quieta to install to my home screen and behave like an app —
its own icon, no Safari chrome, correct spacing around the notch and home bar — **so that** I can
open it the way I open any other app instead of hunting for a browser tab.

**As an** iPhone visitor who taps "Get the app", **I want** to be told how to get Vox Quieta on
*my* phone, **so that** I don't land on a page whose only call to action is Google Play.

## Why

Today an iPhone is a second-class citizen in three specific, verifiable ways:

1. **There is no web app manifest and no service worker.** `frontend/public/` contains
   `app-icon.png`, `app-hero.png`, `changelog.json`, `legal/`, and `about/` — no `manifest.json`,
   no `sw.js`. "Add to Home Screen" therefore produces a bookmark that opens in full Safari
   chrome with a screenshot-derived icon, not an app-like launcher.
2. **The safe-area CSS that exists is inert on iOS.**
   `frontend/src/app/globals.css:57-62` pads `.sticky.bottom-0` (the chat input,
   `ChatIsland.tsx:1162`) by `env(safe-area-inset-bottom)`. But the viewport export at
   `frontend/src/app/[locale]/layout.tsx:46-50` sets only `width`, `initialScale`, and
   `maximumScale` — **no `viewportFit: "cover"`**. Without it iOS resolves every
   `safe-area-inset-*` to `0px`, so the `@supports` guard passes (the property *is* supported)
   while the rule adds nothing. Today that is merely dead code; the moment the app runs in
   standalone display mode it becomes a real overlap, because standalone mode *does* extend the
   page under the home-gesture bar. Adding the manifest without fixing the viewport would ship
   the bug, not just the dead code.
3. **`/app` is a dead end on iOS.** `frontend/messages/en.json` → `App.ctaButton` is
   `"Get it on Google Play"` and `App.ctaSub` is `"Free on Android"`. An iPhone visitor who
   follows the footer's "Get the app" link is told, in eleven languages, that the app is for
   somebody else's phone.

None of this needs a decision about the native app (BITB-085). It is the baseline every option
sits on top of: if the native path is chosen, this is the fallback for users who don't install;
if a WebView wrapper is ever chosen, this *is* the shell it wraps.

## Scope

### Part A — Web app manifest

Add a manifest via Next.js's App Router convention (`src/app/manifest.ts`, so it is typed and
picks up `metadataBase` from `src/app/layout.tsx:6-8`) rather than a hand-written
`public/manifest.json`:

- `name` / `short_name` / `description` — sourced from existing i18n `Metadata` keys where
  possible, not re-invented.
- `display: "standalone"`, `start_url`, `scope`, `background_color`, `theme_color` matching the
  gradient shell in `[locale]/layout.tsx:107-111`.
- `icons`: 192px, 512px, **and a 512px `purpose: "maskable"`** variant. `public/app-icon.png` is
  the source of truth for the artwork — do not draw a new icon.
- `lang` / `dir` cannot be static: the app has 11 locales including RTL Arabic. Either emit a
  per-locale manifest or omit `lang` and let the document supply it. **Decide explicitly and
  write down why**, rather than shipping a hardcoded `"en"`.

### Part B — iOS standalone correctness

- Add `viewportFit: "cover"` to the `viewport` export in `[locale]/layout.tsx:46-50`.
- Verify every `env(safe-area-inset-*)` consumer still looks right once the insets are non-zero —
  today there is exactly one (`globals.css:57-62`), and it will change appearance on iPhone the
  moment this lands. Extend to top/left/right insets where the header or panels now sit under the
  notch or in the landscape ear regions.
- Add `apple-touch-icon` (180×180) and `apple-mobile-web-app-*` metadata through Next's
  `metadata.appleWebApp`, not raw `<meta>` tags.
- Confirm behaviour with `maximumScale: 5` retained — do **not** set `userScalable: false` or
  `maximumScale: 1` to "fix" input zoom; that breaks accessibility (WCAG 1.4.4) and Apple
  ignores it in standalone mode anyway. If iOS input zoom is objectionable, fix it with a
  ≥16px font size on the chat input.

### Part C — Offline shell (service worker) — deliberately minimal

Cache the app shell and static assets only. Explicitly **do not** cache `POST /api/v1/chat/stream`
or any Turnstile-gated response (`X-Turnstile-Token` is single-use — see
`android/.../interceptors/TurnstileInterceptor.kt`); a cached SSE stream or a replayed token is a
correctness bug, not a feature.

- Offline fallback page telling the user chat needs a connection, in their locale.
- Scripture `GET` endpoints (`/api/v1/scripture/translations`, `/scripture/book-names`,
  `/scripture/chapter/{book}/{chapter}`) are safe to cache stale-while-revalidate and are the
  highest-value offline win.
- A cache-busting/versioning story tied to the build, so a deploy cannot leave users pinned to a
  stale shell. This is the single biggest risk in Part C — an un-versioned service worker is how
  you ship an unfixable bug.

> **If Part C threatens the timebox, split it out.** Parts A + B alone deliver installability and
> correct rendering; Part C is an enhancement and can become its own story.

### Part D — `/app` page and footer

- `[locale]/app/page.tsx` gains an iOS branch: "Add to Home Screen" instructions (Share → Add to
  Home Screen), ideally detected rather than making the user self-select.
- New i18n keys for the iOS instructions across **all 11 locales** (`frontend/messages/*.json`).
  Follow the existing `App.*` key namespace.
- Keep the Play badge exactly as-is for Android/desktop. Do **not** add an App Store badge — there
  is no App Store listing yet, and a badge linking nowhere is worse than no badge (BITB-088 adds it).

## Acceptance Criteria

- [ ] `GET /manifest.webmanifest` returns a valid manifest; Chrome DevTools → Application →
      Manifest reports zero errors and an installable state.
- [ ] Adding to Home Screen on iOS Safari yields the Vox Quieta icon (not a page screenshot) and
      launches with no Safari chrome.
- [ ] In standalone mode on a notched iPhone, the chat input clears the home-gesture bar and the
      header clears the notch, in both portrait and landscape, in LTR **and** RTL (`ar`) layouts.
- [ ] `viewportFit: "cover"` is set, and every existing `env(safe-area-inset-*)` rule has been
      re-checked against non-zero insets.
- [ ] Pinch-zoom still works (`maximumScale: 5` unchanged; `userScalable` not disabled).
- [ ] Offline (airplane mode) opening the installed app shows the localized offline fallback, not
      a Safari error page. Chat requests are never served from cache.
- [ ] No `POST` request and no response carrying/consuming `X-Turnstile-Token` is cached.
- [ ] A new deploy invalidates the shell cache — a user with the app open gets the new build on
      next launch without manually clearing site data.
- [ ] `/app` shows iOS install instructions to iPhone visitors and the Play badge to everyone
      else; both paths are localized in all 11 locales.
- [ ] No App Store badge or "coming to iOS" promise ships in this story.

## Tests to Add

- `frontend/src/app/manifest.test.ts` — manifest route returns required fields, all icon paths
  resolve to files that exist in `public/`, and the maskable icon is present.
- Extend the `[locale]/layout` test surface to assert the `viewport` export includes
  `viewportFit: "cover"` — this is a one-line regression that a future refactor will silently drop.
- `frontend/src/app/[locale]/app/page.test.tsx` — iOS branch renders install instructions and does
  *not* render an App Store link; non-iOS branch renders the Play badge.
- Parametrized i18n test that every new `App.*` key exists in all 11 `frontend/messages/*.json`
  files (mirrors the Android `translation-validation` CI job, which has no web counterpart for
  new keys).
- Service-worker tests: cache-name changes with the build id; a `POST` to `/api/v1/chat/stream`
  bypasses the cache. Playwright (`frontend/e2e/`) is the right home for the offline-fallback
  assertion — `frontend/playwright.config.ts` already exists.

## Files Likely to Change

| File | Change |
|---|---|
| `frontend/src/app/manifest.ts` | **New** — typed web app manifest |
| `frontend/src/app/[locale]/layout.tsx` | `viewportFit: "cover"`; `metadata.appleWebApp` |
| `frontend/src/app/globals.css` | Re-check/extend safe-area rules for non-zero insets |
| `frontend/public/` | 192/512/maskable/apple-touch icons derived from `app-icon.png` |
| `frontend/public/sw.js` (or a build-generated equivalent) | **New** — shell + scripture GET caching |
| `frontend/src/app/[locale]/app/page.tsx` | iOS install-instructions branch |
| `frontend/messages/*.json` (11) | New `App.*` iOS keys + offline fallback copy |
| `frontend/e2e/` | Offline-fallback spec |

## Out of Scope

- Web Push. iOS supports it only for home-screen-installed PWAs, and **the product has no push
  anywhere today** — `android/app/src/main/AndroidManifest.xml:5-6` requests only `INTERNET` and
  `ACCESS_NETWORK_STATE`, with no Firebase Messaging dependency. Adding push here would make iOS
  the first platform with a notification permission prompt and a new privacy disclosure, which is
  a product decision, not a side effect of a manifest.
- Offline *chat*. The answer comes from an LLM over the network; there is nothing to cache.
- Any Swift, Xcode, or App Store work — BITB-085 onward.
- Fixing the unreachable footer on the chat page. That is **BITB-079** (P1, already filed) and it
  is a genuine prerequisite for the `/app` funnel being reachable at all from the chat page; do not
  silently absorb it here.

## Related

- **BITB-079** — the bottom bar is off-screen on the chat page; the funnel this story improves is
  only reachable once that is fixed.
- **BITB-085** — the delivery-approach decision this story deliberately does not pre-empt.
- **BITB-088** — adds the App Store badge to `/app` once a listing exists.
- **Icebox → "Offline Mode (Web): Service worker for offline scripture access"** — Part C is the
  concrete version of that idea; remove it from the Icebox if this ships.
