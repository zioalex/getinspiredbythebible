# iOS Delivery Approach — Provisional Decision Record (BITB-085)

**Status:** Provisional as of 2026-09-05; the required Turnstile device probe has not been executed.
**Recommendation:** Option C, native SwiftUI, only if every hard prerequisite below passes. This is
not a framework commitment or authorization to start BITB-087.
**Sequence:** BITB-084 → **BITB-085** → BITB-086 → BITB-109 → BITB-087 → BITB-088.

BITB-087 remains unscheduled. It cannot start until BITB-085 closes, BITB-086 and BITB-109 are done,
and the Turnstile WKWebView probe records an observed pass on a physical iPhone.

## Why this exists

Three contradictory strategies with no reasoning: `docs/ROADMAP.md` ("native iOS app"), BITB-012 Out of Scope ("future consideration"), `docs/ARCHITECTURE.md` ("React Native", stale since Android shipped native Kotlin/Compose). This record replaces all three.

PWA-only (BITB-084) is the floor every option must beat, not a candidate: shippable with no Apple account, but no App Store presence and Share-sheet install friction.

## Options rated against the 7 criteria

### A. PWA only — baseline

Beats nothing by definition; keeps zero store tax. Ceiling is discoverability/credibility for a faith-audience app. Already shipping as BITB-084 (manifest, safe areas, `/app` iOS CTA; offline shell split to BITB-102).

### B. WebView wrapper (Capacitor / hand-rolled WKWebView) — rejected

Inherits the TypeScript parser (no fourth grammar) but fails on two measured facts: `frontend/next.config.js` sets `output: "standalone"` (Node server, not a static export) and locale routing runs through `frontend/middleware.ts` (`next-intl/middleware`), so bundling offline is a real refactor; pointing at the live site is the shape Apple rejects under Guideline 4.2 unless native capability (offline history, share sheet, settings) is added — the work that makes B stop being cheap.

### C. Native SwiftUI — provisional recommendation

Best UX and safest 4.2 standing if the feasibility gates pass. The port is mechanical: clean MVVM Android app, 8-endpoint surface in `android/app/src/main/kotlin/org/voxquieta/app/data/remote/api/BibleApiService.kt`, SSE rules isolated in `.../data/streaming/EventSourceParser.kt`, Room DAOs in `data/local/`, DI boundaries in `di/`. Costs the full third-client tax (255 strings × 11 locales = 2,805 strings; second store relationship via `android-publish.yml` precedent) **unless BITB-086 and BITB-109 land first** — hence the gates.

### D. KMP shared core + SwiftUI UI — deferred

Structurally the best answer to audit A1/BITB-059 (shared domain/remote/streaming/grammar), but front-loads an invasive restructure of a mature, heavily-CI'd Android module (Hilt, KSP, Room, AGP 9.0 built-in Kotlin per `android/app/build.gradle.kts:1-12`) plus KMP toolchain debt for a single maintainer. Bigger near-term risk than duplicated view models. Revisit after iOS v1.

## Weighted score matrix

Scores use `0` (does not meet the goal) through `5` (best fit). Each cell is
`score / weighted points`; weighted points are `weight × score / 5`. The maximum is 100. Option C's
scores assume its named gates pass; failed gates invalidate the score rather than lowering it after
implementation starts.

| Criterion | Weight | Evidence | A: PWA | B: WebView | C: SwiftUI | D: KMP |
|---|---:|---|---:|---:|---:|---:|
| Avoid a fourth parser | 25% | Three regex dialects already drift; `api/chat/service.py` emits spans, but no client proves them yet | 5 / 25 | 5 / 25 | 5 / 25* | 5 / 25 |
| App Store 4.2 risk | 20% | A has no listing; B resembles a repackaged site; C/D provide native chat, history, accessibility, and settings | 0 / 0 | 1 / 4 | 5 / 20 | 5 / 20 |
| Time to maintainable TestFlight | 15% | B needs either a static-export refactor or native mitigations; C ports a bounded API; D migrates Android first | 5 / 15 | 3 / 9 | 3 / 9 | 1 / 3 |
| Ongoing feature cost | 15% | A/B reuse web; C duplicates view models; D shares domain/data code | 5 / 15 | 3 / 9 | 3 / 9 | 5 / 15 |
| Risk to shipping Android | 10% | C is isolated under `ios/`; D restructures the Hilt/KSP/Room Android module | 5 / 10 | 5 / 10 | 5 / 10 | 1 / 2 |
| Localization reuse | 8% | Web strings are reused by A/B; C needs generated Apple catalogs; D can share more resources | 5 / 8 | 5 / 8 | 2 / 3.2 | 4 / 6.4 |
| Single-maintainer fit | 7% | Mechanical ports are easier to review than a new cross-platform toolchain | 5 / 7 | 3 / 4.2 | 4 / 5.6 | 1 / 1.4 |
| **Total** | **100%** | | **80.0 (ineligible)** | **69.2** | **81.8*** | **72.8** |

`*` Option C receives the parser score only after BITB-086 ships the contract and BITB-109 proves it
in the web client. Option A is a useful baseline but is ineligible because it does not meet the App
Store-distribution objective. The narrow lead for C over that baseline is not a commitment; the
unexecuted Turnstile probe can still disqualify C.

## Hard prerequisites

Every open item has the same accountable owner because this is currently a single-maintainer
project. Dates are targets, not claims of completion.

| State | Prerequisite | Owner | Target date |
|---|---|---|---|
| [ ] | Execute and record the physical-iPhone Turnstile probe in `turnstile-wkwebview-probe.md`; no result has been observed yet | Maintainer | 2026-09-12 |
| [ ] | Complete BITB-086's server-emitted citation contract | Maintainer | 2026-09-18 |
| [ ] | Complete BITB-109's web consumer and parity/corrupt-span tests; this is a hard prerequisite, not a fast-follow for iOS | Maintainer | 2026-10-02 |
| [ ] | Enroll in the Individual Apple Developer Program and record the listing developer name | Maintainer | 2026-09-19 |
| [ ] | Reserve the App Store Connect record and candidate bundle `org.voxquieta.app` | Maintainer | 2026-09-26 |
| [ ] | Record hosted macOS runner cost and confirm the budget | Maintainer | 2026-09-12 |
| [ ] | Validate `fastlane match` as the signing strategy and identify certificate-repository access | Maintainer | 2026-09-26 |
| [x] | Exclude Ko-fi/donation entry points from iOS v1 under Guideline 3.2.1(vi) | Maintainer | 2026-09-04 |

## Fourth-parser answer

BITB-086 **and BITB-109** are hard prerequisites of BITB-087. iOS ships **no verse regex** (CI grep-enforced per BITB-087), consuming `citations` spans via substring search and degrading to plain text when absent. BITB-109 must first prove parity, fallback, and corrupt-span behavior in the web client; backend-only tests are not sufficient evidence for an iOS dependency.

## What would reverse this

Turnstile unobtainable in WKWebView; App Store pre-review signals 4.2 risk for the Tier-1 slice; macOS CI cost prohibitive; or BITB-086/BITB-109 proving the span contract unshippable — any of which rejects the provisional recommendation and requires the matrix to be rerun.
