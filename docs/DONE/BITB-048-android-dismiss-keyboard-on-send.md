# BITB-048: Auto-Dismiss Keyboard After Sending a Message (Android)

**Status:** ✅ Done
**Priority:** P2 (Medium) — visible UX friction on every message
**Size:** S (< 1 hr)
**Created:** 2026-06-12
**Source:** Beta tester feedback (Oliver Osthoever, 2026-06-11)

## User Story

**As an** Android user,
**I want** the keyboard to disappear after I tap Send,
**so that** I can see the full response without manually dismissing the keyboard.

## Problem

> "Es nervt ein wenig, dass wenn ein Prompt beantwortet wurde die Hälfte des Displays immer noch
> von der Tastatur überlagert ist und man diese erst wegdrücken muss…"

After tapping Send, the soft keyboard stays open and covers the lower half of the screen. The
`OutlinedTextField` in `ChatInputField.kt` uses `ImeAction.Default` (multi-line, Enter = newline)
and the Send button's `onClick` never clears focus, so the IME stays up. `imePadding()` shifts the
layout but does not hide the keyboard.

## Approach

Clear focus programmatically after a successful submit, which dismisses the IME while keeping the
multi-line input behaviour intact.

## Acceptance Criteria

- [ ] After tapping Send, the keyboard collapses immediately.
- [ ] The full response area is visible without manual dismissal.
- [ ] Enter still inserts a newline (multi-line unchanged).
- [ ] While streaming, the button still shows the Stop icon (no regression).

## Files / Config

| Item | Location | Change |
|---|---|---|
| Input field | `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatInputField.kt` | add `LocalFocusManager`; call `focusManager.clearFocus()` after `onSend(value)` in `submit()` |

## Implementation Notes

```kotlin
import androidx.compose.ui.platform.LocalFocusManager
// …
val focusManager = LocalFocusManager.current
fun submit() {
    if (value.isNotBlank() && canSend) {
        onSend(value)
        focusManager.clearFocus()   // dismiss the IME
    }
}
```

`LocalFocusManager` is already on the classpath (`androidx.compose.ui.platform`); no new dependency.

## Testing

- `ChatInputField` Compose test (`*ComposeTest.kt`): enter text, click Send, assert the field loses
  focus (keyboard-dismissal proxy) and `onSend` fired with the text.
- Manual: type → Send → keyboard collapses; type multi-line with Enter → newline, no submit.

## Related

- `android/COMPOSE_TESTS.md` — Compose UI test tier.
