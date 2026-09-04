# BITB-085: Decide the iOS Delivery Approach — Committed Decision Record + Apple Prerequisites

**Status:** 🚧 In Progress (decision recorded in `docs/ios/delivery-approach.md` 2026-09-04; Turnstile device proof + Apple account pending)
**Priority:** P2
**Size:** S–M (1 day of analysis + the account/tooling setup it unblocks)
**Created:** 2026-07-29
**Part of:** the iOS delivery plan — Stage 1 of BITB-084 → **BITB-085** → BITB-086 → BITB-087 → BITB-088.
**Gates:** BITB-087 and BITB-088 must not start before this closes.

## User Story

**As the** maintainer, **I want** the iOS approach chosen once, in writing, against explicit
criteria, **so that** the multi-week build in BITB-087 is not restarted halfway through because the
UI framework, the shared-code strategy, or the App Store review risk was never actually settled.

## Why This Is a Story and Not Just "Start Building"

The roadmap has carried "**iOS App**: Native iOS app with same features as Android"
(`docs/ROADMAP.md:219`) and "iOS app (future consideration)"
(BITB-012's *Out of Scope* in `docs/BACKLOG.md`) for months with no analysis behind either line. Meanwhile `docs/ARCHITECTURE.md:926` still lists the planned mobile app as **React Native** —
a third answer, and a stale one, since Android shipped as native Kotlin/Compose. Three documents,
three implied strategies, zero recorded reasoning. The first deliverable of the iOS effort is
therefore a decision, not code.

The cost being committed is not the first release; it is the **permanent third-client tax**:

- **255 strings × 11 locales.** `android/app/src/main/res/values/strings.xml` has 255 `<string>`
  entries and 10 `values-<locale>/` directories beside the default. Android CI already has a
  dedicated `translation-validation` job to stop drift (`.github/workflows/android-ci.yml`). A
  third client makes that a three-way problem.
- **A fourth verse parser.** Verse linkification is client-side regex in all three existing
  clients — `api/utils/verse_parser.py`, `frontend/src/lib/versePatterns.ts`, and
  `android/.../presentation/components/ChatMessageItem.kt` (~lines 104-362). Keeping three in sync
  is the **top-ranked finding of the 2026-07 adversarial audit (A1, CRITICAL)** and the subject of
  **BITB-059**, which is only part-way through Phase 1. Adding a hand-written Swift regex would
  make the repo's worst structural problem measurably worse. **This is the single most important
  input to the decision** — see BITB-086, which exists to remove it as a cost.
- **A second store relationship.** App Store review is a human, rejectable, re-reviewable gate on
  every release, unlike the largely automated Play pipeline this repo has already automated
  (`.github/workflows/android-publish.yml`, `android-promote.yml`).

## Options to Evaluate (with what is already known)

The spike does not start from a blank page. Findings already established while writing this plan:

### A. PWA only (no App Store)

Cheapest, and **already being done as BITB-084** — so it is the baseline, not a competing option.
Its ceiling: no App Store presence or discoverability, no "Download on the App Store" credibility
for a faith-audience app, and install requires the user to know the Share-sheet gesture.
**Treat A as the floor every other option must beat, not as a candidate to pick.**

### B. WebView wrapper (Capacitor / hand-rolled WKWebView)

Superficially the cheapest route to a store listing, and it inherits the TypeScript verse parser
for free (no fourth parser). Two concrete problems found:

1. **The web app cannot be statically exported as it stands.** `frontend/next.config.js` sets
   `output: "standalone"` (a Node server), and locale routing runs through
   `frontend/middleware.ts` (`next-intl/middleware`), which does not exist in a static export.
   Bundling the UI offline is a real refactor, not a config flag.
2. **The alternative — pointing the WebView at the live site — is the exact shape Apple rejects**
   under App Review Guideline 4.2 (minimum functionality: "your app should include features,
   content, and UI that elevate it beyond a repackaged website"). The standard mitigation is to add
   native capability (offline history, share sheet, haptics, native settings) — which is precisely
   the work that makes option B stop being cheap.

Quantify both before rating B. Do not rate it on intuition.

### C. Native SwiftUI (the roadmap's stated intent)

Best UX and the safest App Store standing, and the port is unusually mechanical because the Android
app is already clean MVVM with a thin, well-documented API surface: 8 endpoints in
`android/.../data/remote/api/BibleApiService.kt`, SSE parsing isolated in
`android/.../data/streaming/EventSourceParser.kt`, Room DAOs in `data/local/`, DI boundaries in
`di/`. Costs the full third-client tax above, including a fourth parser unless BITB-086 lands first.

### D. Kotlin Multiplatform shared core + native SwiftUI UI

Structurally eliminates the fourth parser and the duplicated domain/data layer by moving
`domain/`, `data/remote/`, `data/streaming/`, and the verse grammar into a `:shared` module
consumed by both apps. The prize is real — it is a partial answer to BITB-059 — but it front-loads
an invasive restructuring of a mature, heavily-CI'd Android module (Hilt, KSP, Room, AGP 9.0 with
built-in Kotlin per `android/app/build.gradle.kts:1-12`), and adds KMP toolchain debt to a
single-maintainer project. **Rate D honestly against the risk of destabilising the shipping
Android app**, which is the thing most likely to go wrong here.

## Decision Criteria (weight these explicitly, don't just list them)

1. Does it add a fourth verse parser? (Hard constraint — see BITB-086.)
2. App Store approval risk, specifically Guideline 4.2.
3. Time to first TestFlight build, and time to a maintainable steady state (these differ).
4. Ongoing per-feature cost: does shipping a feature become a two-client or three-client job?
5. Risk to the **already-shipping Android app**. Non-negotiable: iOS must not destabilise it.
6. Localization: does it reuse existing translations or create a third copy of 255 strings?
7. Fit for a single maintainer with heavy AI assistance — favour mechanical, reviewable work over
   novel toolchains.

**Working assumption this plan is built on (the spike's job is to confirm or falsify it):**
**C — native SwiftUI, gated on BITB-086 removing the fourth-parser cost** — with D's shared-core
idea deliberately deferred rather than rejected, because the invasiveness of a KMP migration to the
live Android app is a bigger near-term risk than duplicated view models.

## Prerequisites This Story Also Delivers

These are lead-time items; discovering them during BITB-087 wastes days.

- [ ] **Apple Developer Program** enrolment (US$99/yr, individual or organization — note the
      organization route needs a D-U-N-S number and takes materially longer). Record which was
      chosen and the developer-name string that will appear on the listing.
- [ ] **App Store Connect** app record created, bundle id reserved. Mirror the Android
      convention: `applicationId = "org.voxquieta"`
      (`android/app/build.gradle.kts`), so `org.voxquieta.app` or `org.voxquieta` — decide and
      record, because a bundle id cannot be changed after first submission.
- [ ] **Build machine reality check.** Xcode requires macOS. Confirm whether a local Mac exists;
      if not, price GitHub-hosted macOS runners (billed at a multiplier vs. Linux minutes) and
      confirm they are acceptable for a repo whose CI is otherwise Linux-only (19 workflows in
      `.github/workflows/`, none macOS).
- [ ] **Signing strategy** decided: manual certificates/profiles vs. fastlane `match` vs. Xcode
      Cloud. The Android precedent is CI-injected secrets
      (`KEYSTORE_PATH`/`KEYSTORE_PASSWORD`/`KEY_ALIAS`/`KEY_PASSWORD`, resolved in
      `android/app/build.gradle.kts`); prefer the analogous approach for consistency.
- [ ] **Turnstile feasibility spiked for real.** iOS must reproduce the whole state machine in
      `android/.../interceptors/TurnstileInterceptor.kt`: `X-Turnstile-Token` on POSTs only,
      single-use tokens consumed on every attached-token request, 403 → reset widget → wait longer
      → retry exactly once, fail-open on timeout. The token comes from a hidden WebView rendering
      the Cloudflare widget (`android/.../presentation/components/TurnstileWebView.kt`). **Verify a
      WKWebView can obtain a token against the production site key before committing to a native
      client** — if it cannot, every POST endpoint is unreachable and the whole plan changes.
- [ ] **Donation-link decision recorded.** BITB-074 plans an in-app "Support us" link to Ko-fi.
      Apple treats donations far more restrictively than Google Play's carve-out that BITB-074
      relies on (Guideline 3.2.1(vi) limits donation collection to approved nonprofit
      organizations; non-nonprofits are pushed to in-app purchase, and external purchase links are
      an entitlement-gated exception). **The default for iOS v1 is: no donate entry point in the
      app.** Record that decision here so BITB-074 does not quietly add one and trigger a
      rejection.

## Acceptance Criteria

- [ ] A committed decision record at `docs/ios/delivery-approach.md` (create `docs/ios/`, mirroring
      the existing `docs/android/`) containing: the four options, each rated against all seven
      criteria with evidence (not adjectives), the decision, the reasoning, and the conditions that
      would reverse it.
- [ ] The fourth-parser question is answered concretely: either BITB-086 is a stated hard
      prerequisite of BITB-087, or the record explains precisely how the chosen option avoids a
      fourth grammar.
- [ ] Every prerequisite checkbox above is either done or has a named owner and a date.
- [ ] The Turnstile WKWebView feasibility question is answered by an **actual test** — a token
      obtained (or provably not obtainable) — not by reading documentation.
- [ ] `docs/ROADMAP.md:219` and `docs/ARCHITECTURE.md:926` are corrected to point at this decision
      record, so the repo stops carrying three contradictory iOS strategies.
- [ ] BITB-087's size/scope in `docs/BACKLOG.md` is revised to match the chosen option, rather than
      left at the placeholder estimate.
- [ ] A `docs/ios/app-store-compliance.md` stub exists, modelled on
      `docs/android/play-console-compliance.md`, ready for BITB-088 to fill in.

## Tests to Add

Documentation-and-setup story with no production code, so the *code* testing rule does not bind.
Two verification artifacts are still required — a decision with no evidence is the failure mode
this story exists to prevent:

- The Turnstile feasibility result must be reproducible: commit the throwaway probe (or its exact
  steps) under `docs/ios/` so the next person can re-run it when the site key rotates.
- If any option is rejected on a measured cost (static-export effort, macOS CI minutes), the
  measurement goes in the record.

## Out of Scope

- Writing production Swift. This story may produce a throwaway Turnstile probe and nothing else.
- Choosing analytics/crash reporting vendors — BITB-087.
- Store listing copy, screenshots, privacy answers — BITB-088.

## Related

- **BITB-084** — the PWA baseline every option must beat.
- **BITB-086** — the prerequisite that makes a native client affordable.
- **BITB-059** — the parser-unification story whose scope this decision directly affects.
- **BITB-012** — the Android → production story; the precedent for how this repo takes an app to a
  store, and the story whose *Out of Scope* line ("iOS app — future consideration") this closes.
- **BITB-074** — the Ko-fi donation link that must not ship on iOS without an explicit decision.
- `docs/audits/2026-07-adversarial-audit.md` — finding A1 (three-parser drift, CRITICAL).
