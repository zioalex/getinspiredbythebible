# BITB-035: Interruptible Chat Streaming & Multi-line Input (Web + Android)

## User Story

As a user of either the web app or the Android app, I want to:

1. **Interrupt a chat response** as soon as I realise I asked the wrong
   question or the answer is going off-track, so I don't have to wait
   for the full reply to finish before I can ask something better.
2. **Write multi-line messages** using `Shift+Enter` (web) or `Enter`
   (Android keyboard) so I can structure longer prayer requests, paste
   passages, or compose questions with line breaks — without
   accidentally sending the message half-typed.

…so chatting feels as responsive and natural as in the LLM apps users
already know (ChatGPT, Claude, Gemini), instead of forcing me to commit
to every message the moment I tap Send.

## Problem

### Before this story

**Web (`frontend/src/app/[locale]/page.tsx`)**

- The composer was a single-line `<input type="text">`. There was no way
  to insert a line break — Enter always submitted.
- Once a stream started, the only way to "stop" was to refresh the page
  or wait until completion. The fetch had no `AbortSignal`, and the Send
  button was disabled while `isLoading` was true, with no Stop affordance.

**Android (`android/app/src/main/kotlin/.../ChatInputField.kt`)**

- The text field used `KeyboardOptions(imeAction = ImeAction.Send)`,
  so the on-screen keyboard's Enter key fired a submit instead of
  inserting a newline. `maxLines = 5` allowed multi-line *display* but
  there was no way for the user to actually type a newline.
- The `ChatViewModel` `sendMessage` launch was not retained, so there
  was no handle to cancel an in-flight SSE stream. The Send `IconButton`
  was simply disabled while loading.

The mismatch with mainstream chat UIs made the product feel less
trustworthy for longer / multi-paragraph spiritual questions and
amplified frustration when the user noticed a typo or wrong wording
mid-response.

## Proposed Changes

### Web frontend

1. **Add `AbortSignal` support to the streaming client.**
   `frontend/src/lib/api.ts` — `streamMessage()` accepts an optional
   `signal: AbortSignal`, passes it to `fetch`, and short-circuits the
   read loop when `signal.aborted` flips (also cancelling the
   `ReadableStreamDefaultReader`).

2. **Wire an `AbortController` per send.**
   `frontend/src/app/[locale]/page.tsx` — `submitMessage` creates a new
   `AbortController`, stores it in `abortControllerRef`, passes
   `controller.signal` into `streamMessage`, and clears the ref on
   success. The `catch` distinguishes user-initiated aborts
   (`AbortError` / `signal.aborted`) from real errors — abort silently
   keeps the partial assistant reply and does **not** surface an error
   message.

3. **Stop button replaces Send while loading.**
   When `isLoading` is true the composer renders a `Square`
   (Lucide-react) icon button that calls `controller.abort()`. When
   idle, the existing Send button is shown.

4. **Multi-line composer.**
   `<input type="text">` becomes a `<textarea>` with:
   - `rows={1}` and an `useEffect` that resizes the element up to a
     ~160 px cap (≈8 lines) as the user types.
   - `onKeyDown` handler: `Enter` submits, `Shift+Enter` inserts a
     newline. `e.nativeEvent.isComposing` is checked so CJK IMEs aren't
     disrupted.
   - `disabled` is gated only by `showSessionLimitButton` (not by
     `isLoading`) so the user can already start drafting the next
     question while a reply streams.

5. **i18n: `Chat.stopGenerating`** added to all 11 locale files
   (`en, ar, de, es, fr, hi, it, ko, pt, ru, zh`) for the Stop button's
   accessible label / tooltip.

### Android app

1. **Retained stream job + `cancelStream()`.**
   `ChatViewModel.kt` stores the streaming coroutine in a
   `streamJob: Job?` field. New public method `cancelStream()` cancels
   the active job. The existing `onCompletion` already runs on
   cancellation and persists `accumulatedContent` plus
   `finalVerses` / `finalVersesCited`, so the partial assistant message
   stays in the conversation history.

2. **Multi-line keyboard.**
   `ChatInputField.kt` switches from `ImeAction.Send` to
   `ImeAction.Default`, removing `KeyboardActions(onSend = …)`. The
   on-screen keyboard's Enter key now inserts a newline (multi-line up
   to the existing `maxLines = 5`). Submission is exclusively via the
   Send icon button.

3. **Send → Stop icon swap.**
   While `isLoading` is true the trailing `IconButton` shows
   `Icons.Filled.Stop` and invokes `onStop` (wired in `ChatScreen.kt` to
   `viewModel::cancelStream`). When idle, the existing
   `Icons.AutoMirrored.Filled.Send` button is shown with its enable/
   disable logic unchanged.

4. **Keep field editable while loading** — `enabled = !isSessionLimitReached`
   only (not `!isLoading`), matching the web behaviour so the user can
   pre-type the next question.

5. **i18n: `chat_stop_button`** added to all 11 `values*/strings.xml`
   (`values`, `values-ar`, `values-de`, `values-es`, `values-fr`,
   `values-hi`, `values-it`, `values-ko`, `values-pt`, `values-ru`,
   `values-zh`). A new resource (rather than reusing `action_cancel`)
   keeps the semantics of "Cancel" untouched elsewhere in the app —
   same rationale as BITB-033.

## Files Changed

| Area | File |
|------|------|
| Web | `frontend/src/lib/api.ts` |
| Web | `frontend/src/app/[locale]/page.tsx` |
| Web | `frontend/messages/{en,ar,de,es,fr,hi,it,ko,pt,ru,zh}.json` |
| Android | `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatInputField.kt` |
| Android | `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/ChatScreen.kt` |
| Android | `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt` |
| Android | `android/app/src/main/res/values{,-ar,-de,-es,-fr,-hi,-it,-ko,-pt,-ru,-zh}/strings.xml` |

## Acceptance Criteria

### Web

- [ ] Typing `Shift+Enter` inserts a newline; typing `Enter` submits.
- [ ] The textarea grows as the user types and caps at ~8 lines with
      its own inner scroll.
- [ ] While a response is streaming, the Send button is replaced by a
      Stop button.
- [ ] Clicking Stop interrupts the SSE stream immediately and the
      partial reply remains visible in the conversation.
- [ ] No error toast / red message is shown when the user stops the
      stream themselves.
- [ ] CJK IME composition is not broken (composing Enter still commits
      the candidate without submitting the message).
- [ ] The Stop button label/tooltip is localised in all 11 supported
      languages.

### Android

- [ ] The on-screen keyboard's Enter key inserts a newline in the
      composer (no submission).
- [ ] While a response is streaming, the trailing icon button shows a
      Stop icon; tapping it cancels the stream.
- [ ] The partial assistant message accumulated up to the moment of
      cancellation remains in the conversation and is persisted to
      Room.
- [ ] The composer remains editable while a reply is streaming so the
      user can pre-type the next message.
- [ ] The Stop icon's content description is localised in all 11
      supported languages.
- [ ] Existing `ChatViewModelTest` tests continue to pass.

## Out of Scope

- Resuming a cancelled response or re-running the same prompt
  automatically (the user can manually retry).
- Showing an explicit "(stopped)" suffix on the partial reply — the UI
  already exits the loading state, which is signal enough.
- Server-side cancellation telemetry (the backend already sees the
  dropped connection; no new metric introduced in this story).
