# BITB-033: Android — Rename Post-Send "Cancel" Button to "Done"

## User Story

As an Android user who has just sent a diagnostic report or a contact
message, I want the dismiss button on the success screen to read "Done"
instead of "Cancel", so it's clear my submission was accepted and that
I'm just closing the panel — not undoing my message.

## Problem

Both bottom sheets show a success screen after a submission succeeds, and
both reuse `R.string.action_cancel` ("Cancel") for the only action on
that screen:

- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/DiagnosticReportBottomSheet.kt:119-121`
  ```kotlin
  Button(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
      Text(stringResource(R.string.action_cancel))
  }
  ```
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ContactFormBottomSheet.kt:140-142`
  ```kotlin
  Button(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
      Text(stringResource(R.string.action_cancel))
  }
  ```

The success state is entered when the shared `ContactFormState.Success`
is emitted (`ContactFormBottomSheet.kt:49-54`).

The word "Cancel" implies the action can be undone. Post-send, that's
misleading — the email has already been delivered.

## Proposed Changes

### 1. Add a new string resource — do **not** rename `action_cancel`

`action_cancel` is used in many other places where "Cancel" is the
correct word (e.g. back-arrow content description in
`SettingsScreen.kt:92`, dismissive actions in conversation flows).
Adding a new key is cheaper and safer than churning every call site.

Add to `android/app/src/main/res/values/strings.xml`:

```xml
<string name="action_done">Done</string>
```

Add to all 10 locale variants (`values-de`, `values-ru`, `values-zh`,
`values-hi`, `values-ar`, `values-pt`, `values-ko`, `values-fr`,
`values-it`, `values-es`).

**Proposed translations** (have these reviewed through the existing
translation flow — they're reasonable starting points):

| Locale | Value |
|---|---|
| de | Fertig |
| ru | Готово |
| zh | 完成 |
| hi | हो गया |
| ar | تم |
| pt | Concluído |
| ko | 완료 |
| fr | Terminé |
| it | Fatto |
| es | Hecho |

### 2. Update the two bottom-sheet success buttons

In `DiagnosticReportBottomSheet.kt:120` and
`ContactFormBottomSheet.kt:141`, swap:

```kotlin
Text(stringResource(R.string.action_cancel))
```

to:

```kotlin
Text(stringResource(R.string.action_done))
```

No other code changes needed — the `onClick = onDismiss` handler is
already correct for "I'm done here, close the sheet".

## Acceptance Criteria

- [ ] Diagnostic report success screen button reads "Done" in English.
- [ ] Contact form success screen button reads "Done" in English.
- [ ] All 10 locale variants of `strings.xml` contain the translated
      `action_done` value.
- [ ] No other usage of `action_cancel` is affected.
- [ ] Manual QA in English and in Arabic (RTL): submit a diagnostic
      report, confirm the button label and that the sheet still dismisses
      correctly.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/DiagnosticReportBottomSheet.kt` | Line 120: swap `action_cancel` → `action_done` |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ContactFormBottomSheet.kt` | Line 141: swap `action_cancel` → `action_done` |
| `android/app/src/main/res/values/strings.xml` | Add `<string name="action_done">Done</string>` |
| `android/app/src/main/res/values-{de,ru,zh,hi,ar,pt,ko,fr,it,es}/strings.xml` | Add translated `action_done` per the table above |

## Out of Scope

- Renaming `action_cancel` itself anywhere else in the app.
- Changing the success-screen copy (`diagnostic_success_title`,
  `diagnostic_success_description`, `contact_success_title`,
  `contact_success_description`).
- Restyling the button (icon, colour) — copy change only.
- iOS app.

## Priority

P3 — Low. Cosmetic clarity fix; the flow already works.

## Size

XS — under 1 hour, including running the translation flow review.

## Dependencies / Related Work

- Builds on BITB-026 (settings UX improvements) and the diagnostic
  report flow introduced in PR #531 / #540.

## Assignee

android-expert
