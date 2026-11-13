---
id: BITB-003
status: done
priority: P1
size: M
rank: 800
---

# BITB-003: Enable Turnstile Bot Protection on Android

**As a** mobile user,
**I want** the Android app to have the same bot protection as the web app,
**so that** the backend remains secure from abuse.

**Acceptance Criteria:**

Android Implementation:

- [x] Hidden `TurnstileWebView` composable created (loads local HTML with Turnstile widget)
- [x] `TurnstileManager` Hilt singleton manages token state (StateFlow)
- [x] `TurnstileInterceptor` (OkHttp) injects `X-Turnstile-Token` header automatically
- [x] `ChatInputField` disables send button while `!isTurnstileReady` (matches web UX)
- [x] WebView configured: JavaScript enabled, DOM storage enabled, cookies enabled
- [x] `turnstile.html` asset created with Cloudflare widget (invisible mode)
- [x] ProGuard rules added to preserve `@JavascriptInterface` methods

Testing & Documentation:

- [x] Unit tests for `TurnstileManager` token state management (`TurnstileManagerTest.kt` — 16 tests)
- [ ] Manual QA: initialization timing, token expiry, offline behavior
- [x] Graceful fail-open when WebView unavailable or network down — `TurnstileManager.hasError`
  state; `ChatViewModel` sets `isTurnstileReady=true` on widget error so the user isn't
  permanently blocked
- [x] Backend validation works unchanged (reuses `api/utils/turnstile.py`)

**Tech Constraints:**

- ❌ **NO official Cloudflare Android SDK** — must use WebView approach (Cloudflare's official recommendation)
- Min SDK 26 (existing constraint) ✅ Compatible
- Zero backend changes required — `X-Turnstile-Token` header already validated
- Token lifetime: 5 minutes (WebView auto-refreshes on expiry via `expired-callback`)

**Implementation Approach (from research):**

1. Create `assets/turnstile.html` with Cloudflare JS widget (invisible, data-size="invisible")
2. `TurnstileWebView` loads HTML, exposes `Android.onToken()` JavaScript bridge
3. `TurnstileManager` singleton holds token as `StateFlow<String?>`, injected via Hilt
4. `TurnstileInterceptor` reads token from manager, adds to every API request header
5. `ChatViewModel` observes `TurnstileManager.isReady` → UI disables send button until ready

**Out of Scope:**

- Custom CAPTCHA implementation (using official Cloudflare widget)
- Separate Turnstile site key for Android (can use same as web initially)
- Backend changes to Turnstile logic

**Dependencies:**

- Requires: Android app bootstrap (PR #156) already merged ✅

**Research Doc:** Task ses_3753a6f4cffezvpl17chuMVTHC (Turnstile Android research)
**Tracking Doc:** `docs/WIP/android-app.md`
