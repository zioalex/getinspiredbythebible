# Language switching: post-mortem of the Compose-only path

## Outcome

**The manual `createConfigurationContext` + `CompositionLocalProvider(LocalContext, LocalConfiguration)` approach never produced a live UI string swap on a real device.** After three iterations (PRs #485, #487, #488, #499 + the #501 diagnostic round), the project pivoted to `AppCompatDelegate.setApplicationLocales(...)` in PR #502, which is the officially supported AndroidX path.

This document records what was tried, why each iteration was believed to work, and what we now think the actual failure mode was.

## Symptoms (consistent across all attempts)

- Picker highlight color changes immediately when a new language is tapped → state in `ChatViewModel.uiState.currentLocale` updates correctly.
- LLM responses arrive in the chosen language → `currentLocale` reaches the `language` parameter on the chat request (`ChatViewModel.kt:365`).
- Every `stringResource(...)` call **stays in the system locale** (English on a US-locale device) — toolbar titles, button labels, conversation list strings, new chat screens after navigation. None of them swap.
- Cold-start path is correct: if you change the device's system language and reopen the app, strings are localized. Only the in-app picker does nothing visible.

## Things ruled out empirically

| Hypothesis | Ruled out by |
|---|---|
| StateFlow doesn't propagate from picker → MainActivity | `selectedLanguage` is `SharingStarted.Eagerly` (`ChatViewModel.kt:165–171`); picker color tracking proves the state changes. |
| Translations missing for chosen locale | `wc -l strings.xml` across all 11 locale folders: 191 strings each, all complete. |
| Pre-existing app version with Play Store signature blocking install | Reproduced even with no other build of the app installed. |
| Compose UI 1.7.6 missing `LocalResources` | Tried bumping `compose-bom` to `2025.04.00`; `androidx.compose.ui.platform.LocalResources` is **not** a public symbol on either version, despite a previous session's commit message claiming otherwise. The compile errors `Unresolved reference 'LocalResources'` confirmed it. |

## What was tried (chronologically)

1. **PR #485** — Override `attachBaseContext` + `recreate()` the Activity on locale change. Reverted: the recreate fired before persistence completed (`LanguagePreferences` async write race), so the recreated Activity read the *old* code from disk and rendered English again.

2. **PR #487, #488** — Pure Compose path: provide `LocalContext` (wrapped via `createConfigurationContext`) + `LocalConfiguration` inside `CompositionLocalProvider`. No Activity recreate. Believed to work; merged. In practice the user observed no UI string change.

3. **PR #499** — Re-attempted strip + persistence-race fixes, including a synchronous `LanguagePreferences.setLanguageSync` so the recreate path would see the new code. Eventually rolled back to the pure Compose-only path again.

4. **PR #501 (diagnostic round, this branch)** — Hypothesised that `stringResource()` in Compose 1.7+ routes through `LocalResources` rather than `LocalContext.current.resources`, and that adding a `LocalResources` provider would close the gap. Build broke with `Unresolved reference 'LocalResources'` because the symbol does not exist as a public CompositionLocal. Bumped BOM to 2025.04.00 — same error. Conclusion: that hypothesis was wrong from the start; a previous session's commit message had asserted the symbol's existence without verifying.

5. **#501 diagnostic logging** — Added a `LaunchedEffect(languageCode)` that logs `languageCode`, `localizedContext.resources.getString(R.string.app_name)`, and `localizedContext.resources.configuration.locales.toLanguageTags()` to logcat (tag `VoxLocale`). Built successfully. Installed on device. Result: language picker still does nothing visible.

## Best current theory of the root cause

Given that:
- `LocalContext.current` and `LocalConfiguration.current` providers are demonstrably set with new values on each `languageCode` change (`remember(languageCode)` re-runs).
- Compose's `stringResource()` ultimately reads `LocalContext.current.resources.getString(id)` (verified in the AOSP `androidx.compose.ui.res.Resources` source).
- The wrapped Resources object built via `activity.createConfigurationContext(localizedConfiguration).resources` *should* return the localized string when called directly.

…then either:

1. **`createConfigurationContext` doesn't actually flip the locale on a fresh `Configuration` built via `Configuration(parent.configuration).also { setLocale(...) }`.** This is plausible: `Configuration.setLocale()` mutates `mLocaleList` in ways that interact with `LocaleList` cache state in non-obvious ways across Android versions. Without the diagnostic log values from the device, we can't confirm whether `wrapper.app_name` == English or Italian after picker tap — that single piece of data would have been decisive. *(Slot left for the reader: paste the `VoxLocale` line here when captured.)*

2. **A downstream `CompositionLocalProvider` re-provides `LocalContext`** with the original Activity context, masking our override. Candidates: `VoxQuietaTheme` internals (Material3), `hilt-navigation-compose`'s `findActivity()` walk, or `NavHost`'s back-stack-entry-scoped composition. We did not exhaustively audit every Compose dependency for re-providers.

Either way, the fix path of the manual approach requires either reverse-engineering Compose internals or maintaining a parallel locale-aware Resources cache — neither of which is worth doing when AndroidX provides `AppCompatDelegate.setApplicationLocales` for free.

## Resolution

**PR #502** switches to `AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(code))`, which causes a single Activity recreate. After recreate, the platform-supplied `Configuration` reflects the chosen locale, so every `stringResource(...)` resolves correctly without any `CompositionLocalProvider` plumbing. The manual `localizedConfiguration` + `localizedContext` block in `MainActivity` (~30 lines) is deleted.

Trade-off accepted: a single ~150ms visual flash per language change. Edge case: in-flight LLM streaming responses are cancelled when the user changes language mid-conversation. Acceptable because the picker lives in Settings, mid-conversation changes are unusual, and the alternative — broken language switching — is worse.

## Lessons

- **Verify external API claims with a build before assuming they're correct.** A previous session's commit message asserted `LocalResources` was a public Compose UI symbol; treating that as ground truth cost two failed CI cycles. A 30-second `grep` of the AOSP source would have caught it.
- **For platform features, prefer the official path.** AndroidX has shipped `setApplicationLocales` precisely because the manual approach is fragile across Android versions and Compose internals churn. Re-implementing it ourselves traded ~30 lines saved against multiple PRs of debugging.
- **Diagnostic logging is cheap; deploy it earlier.** A `LaunchedEffect` that logs `wrapper.resources.getString(...)` should have been in the very first attempt. We could have shipped it with PR #487 and immediately known whether the wrapper Resources were even producing the right string.

## Reference PR trail

- #485 — first attempt, attachBaseContext + recreate (race)
- #487 — Compose-only path introduced
- #488 — live-swap consolidation
- #499 — debug round, persistence-race fixes
- #501 — failed `LocalResources` hypothesis + diagnostic round (this branch)
- #502 — `AppCompatDelegate.setApplicationLocales` (the fix)
