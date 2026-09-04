# Turnstile in WKWebView — Reproducible Feasibility Probe (BITB-085)

**Status:** Procedure committed; device proof pending (owner: maintainer, run before BITB-087 starts).
**Why:** every POST (chat, chat/stream, church/search, feedback, contact) requires `X-Turnstile-Token`. Android proves the machine in `android/app/src/main/kotlin/org/voxquieta/app/data/remote/interceptors/TurnstileInterceptor.kt` (POST-only, single-use consumed on every attached request, 403 → `requestReset()` → exactly one retry, 5s first wait / 8s retry, fail-open). iOS must reproduce it in a `WKWebView` hosting the Cloudflare widget (Android parallel: `.../presentation/components/TurnstileWebView.kt` + `security/TurnstileManager.kt`).

## Re-run steps

1. On a physical iPhone (iOS 17+), fresh install, production site key from `/config`.
2. Load the probe page below in a hidden `WKWebView` (`javaScriptEnabled`, no custom UA).
3. Tap through a chat POST via `URLSession`; assert the request carries `X-Turnstile-Token`.
4. Force a 403 (stale token); assert reset → fresh token → exactly one retry, then fail-open without hanging.
5. Record PASS/FAIL + iOS version + date in this file.

## Minimal probe (Swift, throwaway — keep in sync with Android semantics)

```swift
import WebKit

final class TurnstileProbe: NSObject, WKScriptMessageHandler {
    var token: String?
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        if m.name == "turnstile", let t = m.body as? String { token = t }
    }
    // Load widget page, await token (5s), POST with X-Turnstile-Token,
    // consume (nil it), 403 -> reset + await (8s) -> retry once -> fail open.
}
```

Full Android reference: `TurnstileInterceptor.kt:26-80` (single-use consume + 403-retry-once + fail-open), `TurnstileManager.kt` (token/reset/error flows), `TurnstileWebView.kt` (hidden WebView + `window.resetWidget()` + reload-with-backoff recovery).

## Result log

- [ ] Unrun — maintainer to fill: token obtained? (yes/no), iOS version, date, notes. If NO, BITB-085 decision reopens per `delivery-approach.md`.
