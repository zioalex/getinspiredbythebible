# Turnstile WKWebView Probe — BITB-085 / BITB-087

A minimal, self-contained, dependency-free Xcode app that reproduces the Android
Turnstile reference behavior inside a native iOS `WKWebView`, so the feasibility
probe required by `docs/ios/turnstile-wkwebview-probe.md` is pure execution on the
maintainer's Mac — no design work left to do on the device.

**This is a probe, not the app.** It exists to observe and log the checklist
items below; it is not shippable UI.

## What it mirrors (Android reference)

| Android | Probe file |
| ------- | ---------- |
| `data/remote/interceptors/TurnstileInterceptor.kt` — POST-only attach, single-use consume on every attached request, 403 → `requestReset()` → exactly one retry, 5s/8s bounded waits, fail-open | `TurnstileProbe/ProbeStore.swift` |
| `security/TurnstileManager.kt` — token cache, `hasError`, `requestReset`/`onTokenConsumed` | `TurnstileProbe/TurnstileManager.swift` |
| `presentation/components/TurnstileWebView.kt` + `assets/turnstile.html` — hidden WebView hosting the widget, `window.resetWidget()`, reload-with-backoff error recovery (1s → 8s, 5 attempts) | `TurnstileProbe/TurnstileWebView.swift` (HTML generated in `TurnstileHTML.page(siteKey:)`) |

## The observation checklist (doc steps 3–6)

The app has one button per item; every observation is written to the on-screen,
copy-pasteable, timestamped log:

1. **(a) Obtain token → POST succeeds** — waits up to 5s for the widget, attaches
   the token as `X-Turnstile-Token`, POSTs to the configured URL (default:
   production `https://voxquieta.org/api/v1/chat`), logs the status.
2. **(b) Single-use** — re-attaches the *last* attached token (kept for this test);
   Cloudflare must reject it (`timeout-or-duplicate` → expect 403).
3. **(c) Force 403 → reset → exactly one retry** — sends a deliberately stale token,
   then `requestReset()` → `window.resetWidget()` → fresh token (up to 8s) → one
   retry. The log shows the retry count; pass criterion is `retries == 1`.
4. **(d) Timeout/fail-open** — suppresses token delivery (a test hook), verifies
   the 5s initial and 8s retry waits elapse and the request still goes out
   WITHOUT a token — bounded, logged, no hang.

## Zero-to-running

1. Clone the repo; open `tools/ios-probe/TurnstileProbe.xcodeproj` in Xcode 16+
   (current Xcode is fine — the project uses the synchronized-folder format, no
   SPM dependencies, no CocoaPods).
2. In the simulator/device toolbar pick your physical iPhone (iOS 17+),
   **Signing & Capabilities → set your Team** (automatic signing; the bundle id
   is `org.voxquieta.ios.turnstileprobe`).
3. Get the production site key from `https://voxquieta.org/config`
   (`turnstile_site_key`), paste it into the app's **site key** field (a
   placeholder key ships in `ProbeConfig.swift` for convenience).
4. Press Cmd+R on the physical iPhone. (Simulator runs do NOT satisfy the gate —
   the doc requires a physical device.)
5. Tap the four buttons in order and watch the log; use **Copy all** to grab the
   transcript.
6. Record the observations in the doc's result log: date, device model, iOS
   version, site-key environment, token obtained (yes/no), single-use behavior,
   403 retry count, timeout behavior, and the artifact commit.
7. Tick the result-log checkbox in `docs/ios/turnstile-wkwebview-probe.md` only
   when every criterion above has observed evidence.

### Notes / caveats

- The widget page is loaded with `baseURL = https://voxquieta.org` so Turnstile
  validates the production hostname — the parallel of Android's
  `loadDataWithBaseURL(BuildConfig.FRONTEND_URL, …)`.
- The POST URL is editable in-app; point it at any test endpoint if desired.
- Cannot be compiled on this Linux box: this package was written and reviewed
  statically, never built by Xcode. The first Mac session may surface build
  fixes — if the project does not open cleanly, create a new iOS App target named
  `TurnstileProbe` in Xcode and drag the six `.swift` files from
  `tools/ios-probe/TurnstileProbe/` in; the code has no external dependencies.

## File layout

```text
tools/ios-probe/
  README.md                            ← this file
  TurnstileProbe.xcodeproj/            ← hand-written minimal project (Xcode 16+ format)
  TurnstileProbe/                      ← sources (auto-synced into the target)
    TurnstileProbeApp.swift            ← @main
    ContentView.swift                  ← config fields, checklist buttons, log view
    ProbeConfig.swift                  ← defaults: prod URL, site-key placeholder, 5s/8s
    ProbeLog.swift                      ← timestamped copy-pasteable log
    ProbeStore.swift                    ← interceptor-parity POST path + waits
    TurnstileManager.swift             ← manager parity
    TurnstileWebView.swift             ← WKWebView + JS bridge + reset/backoff
```
