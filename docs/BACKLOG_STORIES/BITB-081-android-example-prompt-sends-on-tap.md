# BITB-081: Android — Tapping an Example Question Must Always Send It on the First Tap

**Status:** ✅ Done (PR #957, merged 2026-08-21) — status marker was left stale; corrected 2026-08-28.
`onExamplePromptTapped` in `ChatScreen` drops the Turnstile-readiness gate, covered by
`ExamplePromptTapTest` and `WelcomeBannerComposeTest`.
**Priority:** P1
**Size:** S (< 4 hrs)
**Created:** 2026-07-25

## User Story

**As an** Android user tapping one of the example questions on the welcome screen,
**I want** it to be sent immediately,
**so that** I get an answer from one tap instead of having the text silently dropped into the input
box and having to find the send arrow.

## Why

This is the app's very first interaction. A new user taps "I feel anxious and can't stop worrying"
expecting an answer; instead the text appears in the composer and nothing happens. Some users tap
the same suggestion again (still nothing sends), some assume the app is broken and leave. The web
version does not have this problem — tapping a starter prompt there calls `submitMessage(prompt)`
directly (`frontend/src/app/[locale]/ChatIsland.tsx:1061-1070`) and sends.

The Android code *intends* to send, but guards the send behind a Turnstile-readiness check that is
frequently false exactly when the welcome screen is on display — cold start, before the Turnstile
WebView has produced its first token.

## Current Behaviour

`android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/ChatScreen.kt:370-382`:

```kotlin
WelcomeBanner(
    onPromptSelected = { prompt ->
        // Tapping a sample question submits it directly.
        // If Turnstile isn't ready yet, fall back to
        // filling the input so the Send button still works.
        if (uiState.isTurnstileReady) {
            viewModel.sendMessage(prompt)
            inputText = ""
        } else {
            inputText = prompt
        }
    },
    ...
)
```

`isTurnstileReady` becomes true only once the WebView delivers a token **or** Turnstile has errored
(fail-open) — `ChatViewModel.kt:262-274`. On a cold start the welcome screen is visible well before
either happens, so the `else` branch runs and the tap becomes a silent paste with no feedback.

**The guard is unnecessary.** `TurnstileInterceptor` already handles a missing token for POSTs: it
waits for one with a bounded timeout (`awaitTokenOrNull()`), attaches it when it arrives, proceeds
without it if it does not, and on a 403 kicks the widget to refresh and retries the request exactly
once (`android/app/src/main/kotlin/org/voxquieta/app/data/remote/interceptors/TurnstileInterceptor.kt:28-79`).
`ChatViewModel.sendMessage` itself (`:379`) has no token precondition — it only refuses when the
text is blank or a send is already in flight. So sending unconditionally is already safe; the
screen-level guard duplicates, and defeats, the transport-level handling.

## Proposed Behaviour

Send on every tap:

```kotlin
onPromptSelected = { prompt ->
    inputText = ""
    viewModel.sendMessage(prompt)
}
```

The message is appended to the conversation immediately with the usual streaming placeholder, so
the user gets instant visual confirmation; the interceptor absorbs the token wait. If the request
ultimately fails, the existing error handling surfaces it — a visible error is a far better outcome
than a silent paste.

Two details to get right:

- **Do not gate on `isSessionLimitReached` here either** — that path already produces its own
  user-visible message.
- **Keep the composer's own send button gated as it is** (`ChatInputField.kt:35,40`,
  `canSend = !isLoading && isTurnstileReady && !isSessionLimitReached`) or reconsider it
  separately. This story is about the example tap; widening it to the composer is a separate
  judgement call about whether the composer should also stop disabling itself during the Turnstile
  warm-up. Note the inconsistency in the story's follow-up if it is left as is.

The same send-on-tap behaviour must apply to the follow-up chips from **BITB-080** when they land.

## Acceptance Criteria

- [ ] Tapping an example question on a **cold start**, before Turnstile has produced a token, sends
      the message and starts streaming a response.
- [ ] The tapped text never remains in the input field.
- [ ] Tapping an example question never requires a second tap or a press of the send arrow.
- [ ] If the backend rejects the request, the user sees the normal error state — never silence.
- [ ] Behaviour is identical whether Turnstile is enabled, disabled, or in its error/fail-open
      state.
- [ ] Web parity: one tap → one sent message on both platforms.

## Tests to Add

- Compose UI test (`./gradlew testDebugCompose`, the **BITB-034** tier): with
  `isTurnstileReady = false`, tapping a `WelcomeBanner` suggestion invokes `sendMessage` and leaves
  the input field empty.
- `ChatViewModel` test: `sendMessage` called with no Turnstile token still appends the user message
  and starts a stream (interceptor behaviour mocked).
- Regression: tapping a suggestion twice in quick succession does not create two conversations
  (guarded by the existing `isLoading` check in `sendMessage`).

## Files Likely to Change

| File | Change |
|---|---|
| `android/.../presentation/screens/ChatScreen.kt` | Remove the `isTurnstileReady` branch in `onPromptSelected` |
| `android/app/src/test/.../` | Compose UI + ViewModel tests |

## Related

- **BITB-080** — follow-up chips must send on first tap for the same reason.
- **BITB-003** — Turnstile on Android (origin of the readiness flag).
- `docs/DONE/PR171-turnstile-ready-fix.md`, `docs/DONE/PR-turnstile-ready-fix.md` — prior fixes in
  this area; worth reading before changing the flag's semantics.
