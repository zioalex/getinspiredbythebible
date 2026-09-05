# Turnstile in WKWebView — Required Feasibility Probe (BITB-085)

**Status:** REQUIRED, NOT YET EXECUTED. No token, iOS behavior, or pass result has been observed.
**Owner:** Maintainer. **Target date:** 2026-09-12. **Blocks:** BITB-085 closure and BITB-087 start.
**Why:** every POST (chat, chat/stream, church/search, feedback, contact) requires `X-Turnstile-Token`. Android proves the machine in `android/app/src/main/kotlin/org/voxquieta/app/data/remote/interceptors/TurnstileInterceptor.kt` (POST-only, single-use consumed on every attached request, 403 → `requestReset()` → exactly one retry, 5s first wait / 8s retry, fail-open). iOS must reproduce it in a `WKWebView` hosting the Cloudflare widget (Android parallel: `.../presentation/components/TurnstileWebView.kt` + `security/TurnstileManager.kt`).

## Required execution

This PR does not include a runnable HTML/Xcode probe, so these steps are an execution requirement,
not proof or a reproducible artifact. The owner must create a minimal Xcode app and widget page before
claiming a result.

1. Create a minimal iOS 17+ Xcode app containing a `WKWebView`, local HTML that renders Cloudflare's
   widget, a `WKScriptMessageHandler` token bridge, and a `URLSession` POST path.
2. On a physical iPhone, fresh-install the app and obtain the production site key from `/config`.
3. Obtain an actual token and verify that a POST carries it as `X-Turnstile-Token`.
4. Verify that the attached token is consumed after one request and is not reused.
5. Force a 403 with a stale token; verify widget reset, a fresh token, and exactly one retry.
6. Suppress token delivery; verify 5-second initial and 8-second retry waits fail open without a hang.
7. Commit the runnable probe or an immutable artifact link, then record the observations below.

Reading Cloudflare or WebKit documentation does not satisfy this gate. Simulator-only results do not
satisfy it. Do not mark native SwiftUI committed until every pass criterion has observed evidence.

Full Android reference: `TurnstileInterceptor.kt:26-80` (single-use consume + 403-retry-once + fail-open), `TurnstileManager.kt` (token/reset/error flows), `TurnstileWebView.kt` (hidden WebView + `window.resetWidget()` + reload-with-backoff recovery).

## Result log (observations only)

- [ ] **UNRUN** — no observed result. Record date, device model, iOS version, site-key environment,
      token obtained (yes/no), single-use behavior, 403 retry count, timeout behavior, and artifact
      commit/link. A failure disqualifies option C until resolved.
