# iOS Delivery Approach — Committed Decision Record (BITB-085)

**Status:** Committed 2026-09-04. Part of BITB-084 → **BITB-085** → BITB-086 → BITB-087 → BITB-088.
**Decision:** **C — native SwiftUI, gated on BITB-086** removing the fourth-parser cost. D (KMP shared core) deferred, not rejected.
**Locked by maintainer:** Individual Apple Developer Program ($99/yr) · no local Mac → paid macOS runners acceptable · bundle `org.voxquieta.app` · signing via `fastlane match`.

Gates BITB-087 and BITB-088: neither starts until BITB-086 lands and the Turnstile WKWebView proof below passes.

## Why this exists

Three contradictory strategies with no reasoning: `docs/ROADMAP.md` ("native iOS app"), BITB-012 Out of Scope ("future consideration"), `docs/ARCHITECTURE.md` ("React Native", stale since Android shipped native Kotlin/Compose). This record replaces all three.

PWA-only (BITB-084) is the floor every option must beat, not a candidate: shippable with no Apple account, but no App Store presence and Share-sheet install friction.

## Options rated against the 7 criteria

### A. PWA only — baseline

Beats nothing by definition; keeps zero store tax. Ceiling is discoverability/credibility for a faith-audience app. Already shipping as BITB-084 (manifest, safe areas, `/app` iOS CTA; offline shell split to BITB-102).

### B. WebView wrapper (Capacitor / hand-rolled WKWebView) — rejected

Inherits the TypeScript parser (no fourth grammar) but fails on two measured facts: `frontend/next.config.js` sets `output: "standalone"` (Node server, not a static export) and locale routing runs through `frontend/middleware.ts` (`next-intl/middleware`), so bundling offline is a real refactor; pointing at the live site is the shape Apple rejects under Guideline 4.2 unless native capability (offline history, share sheet, settings) is added — the work that makes B stop being cheap.

### C. Native SwiftUI — chosen (gated)

Best UX and safest 4.2 standing. The port is mechanical: clean MVVM Android app, 8-endpoint surface in `android/app/src/main/kotlin/org/voxquieta/app/data/remote/api/BibleApiService.kt`, SSE rules isolated in `.../data/streaming/EventSourceParser.kt`, Room DAOs in `data/local/`, DI boundaries in `di/`. Costs the full third-client tax (255 strings × 11 locales = 2,805 strings; second store relationship via `android-publish.yml` precedent) **unless BITB-086 lands first** — hence the gate.

### D. KMP shared core + SwiftUI UI — deferred

Structurally the best answer to audit A1/BITB-059 (shared domain/remote/streaming/grammar), but front-loads an invasive restructure of a mature, heavily-CI'd Android module (Hilt, KSP, Room, AGP 9.0 built-in Kotlin per `android/app/build.gradle.kts:1-12`) plus KMP toolchain debt for a single maintainer. Bigger near-term risk than duplicated view models. Revisit after iOS v1.

## Criteria scorecard (evidence, not adjectives)

1. Fourth parser (hard constraint): B passes free; C passes **only** via BITB-086 (backend already computes citations, `api/chat/service.py`, no client consumes `verses_cited`); D passes structurally; A n/a.
2. 4.2 approval risk: C lowest (native streaming chat, offline history, Dynamic Type, 11 locales); B highest (repackaged website); D same as C.
3. Time to TestFlight vs steady state: B fastest to a listing, slowest to a maintainable app once native mitigations pile on; C 2+ weeks (BITB-087 XL confirmed); D slowest (migration first).
4. Per-feature cost: C/D become two/three-client jobs without 086; with 086 + generated strings (BITB-087: script from `strings.xml`/`messages/*.json`, CI key-parity mirroring `translation-validation` in `.github/workflows/android-ci.yml`) C stays bounded.
5. Risk to shipping Android (non-negotiable): C zero (new `ios/`, diff outside `ios/`+script+CI empty per BITB-087); D highest (touches live Android module).
6. Localization: C requires the generator + CI gate, else permanent three-way drift; B reuses web strings; D shares the most.
7. Single-maintainer + AI fit: C favours mechanical, reviewable ports; D favours novel-toolchain risk.

## Prerequisites (owner: maintainer, due before BITB-087 starts)

- [ ] Individual enrollment ($99/yr); record the listing developer-name string.
- [ ] App Store Connect record + bundle `org.voxquieta.app` reserved (immutable after first submission; Android: `applicationId = "org.voxquieta"`, `namespace = "org.voxquieta.app"` in `android/app/build.gradle.kts:15,67`).
- [ ] macOS CI accepted: 21 workflows in `.github/workflows/`, none macOS today; price hosted-runner multiplier vs Linux minutes and record.
- [ ] Signing via `fastlane match` (cert repo + access part of BITB-088); local non-signing tasks must work credential-free, mirroring Android `KEYSTORE_*` fail-closed discipline.
- [ ] Turnstile WKWebView proof: see `docs/ios/turnstile-wkwebview-probe.md`. Must reproduce the full `TurnstileInterceptor.kt` machine (`X-Turnstile-Token` POST-only, single-use consumed every attached request, 5s first wait / 8s retry, 403 → reset → exactly one retry, fail-open). **If no token is obtainable, every POST is unreachable and this decision reopens.**
- [ ] Donations: **no Ko-fi entry point on iOS v1** (Guideline 3.2.1(vi) stricter than the BITB-074 Play carve-out). Recorded so BITB-074 cannot quietly add one.

## Fourth-parser answer

BITB-086 is a hard prerequisite of BITB-087. iOS ships **no verse regex** (CI grep-enforced per BITB-087), consuming `citations` spans via substring search and degrading to plain text when absent. Web becomes the reference consumer first (BITB-109) so the contract is exercised before iOS depends on it.

## What would reverse this

Turnstile unobtainable in WKWebView; App Store pre-review signals 4.2 risk for the Tier-1 slice; macOS CI cost prohibitive; or BITB-086/109 proving the span contract unshippable — any of which reopens B vs C with measurements in this file.
