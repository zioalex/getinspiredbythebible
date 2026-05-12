# Language switching: implementation

## What ships today

The language picker calls `ChatViewModel.setLocale(code)`, which:

1. Updates `uiState.currentLocale` in-memory (consumed by the LLM `language` request parameter).
2. Persists the choice to DataStore via `LanguagePreferences.setLanguage(code)`.
3. Calls `LocaleApplier.apply(code)`, which on **API 33+** invokes the platform
   `LocaleManager.setApplicationLocales(LocaleList.forLanguageTags(code))` directly. The
   platform persists the choice via its own `LocaleManager`/`PackageConfigPersister`, recreates
   the Activity with a `Configuration` reflecting the new locale, and surfaces the choice in
   *Settings → System → Languages → App languages*.

After Activity recreate, every `stringResource(...)` call resolves against
`values-<lang>/strings.xml` automatically — no Compose `CompositionLocalProvider` plumbing for
locale.

## Files involved

| File | Role |
|---|---|
| `android/app/src/main/res/xml/locales_config.xml` | Lists the 11 supported locales (en, ar, de, es, fr, hi, it, ko, pt, ru, zh). Required by the platform per-app-language API. |
| `android/app/src/main/AndroidManifest.xml` | Declares `android:localeConfig="@xml/locales_config"` and the `AppLocalesMetadataHolderService` that AndroidX needs on API ≤32 (currently inert because we go straight to `LocaleManager` on API 33+). |
| `android/app/src/main/kotlin/.../utils/LocaleApplier.kt` | Hilt-injected interface + `AppCompatLocaleApplier` impl. On API 33+ calls platform `LocaleManager`; on API ≤32 falls back to `AppCompatDelegate.setApplicationLocales` (see *Known limitation* below). |
| `android/app/src/main/kotlin/.../presentation/viewmodels/ChatViewModel.kt` | `setLocale(...)` writes state, persists, then calls `localeApplier.apply(...)`. |
| `android/app/build.gradle.kts` | `implementation(libs.androidx.appcompat)` (1.7.0) for the API ≤32 backport path. |

## Why we bypass `AppCompatDelegate.setApplicationLocales` on API 33+

`AppCompatDelegate.setApplicationLocales(...)` requires `AppCompatDelegate` to have been
initialized by an `AppCompatActivity`. Internally it caches a `Context` reference (via
`attachBaseContext2` on `AppCompatDelegateImpl`) which it later uses to fetch the system
`LocaleManager`. Our `MainActivity` extends `ComponentActivity` (the lighter Compose-friendly
base class), so that context is never populated. The result on API 33+ is a silent no-op:
`setApplicationLocales(...)` returns without throwing, but `getApplicationLocaleManager()`
returns `null`, the `LocaleManager` call never happens, and `getApplicationLocales()` reports
empty immediately afterward.

This was confirmed empirically:

```
I VoxLocale: ChatViewModel.setLocale(fr) called
I VoxLocale: AppCompatLocaleApplier.apply(fr) entering; SDK_INT=34
I VoxLocale: AppCompatLocaleApplier.apply done; getApplicationLocales=
```

Calling the platform `LocaleManager` directly via `context.getSystemService(LocaleManager::class.java)`
sidesteps the `AppCompatDelegate` static-context requirement entirely.

## Why we don't switch to `AppCompatActivity`

It's tempting to "just" switch `MainActivity` to `AppCompatActivity` to make `AppCompatDelegate`
work. We don't, because:

- `ComponentActivity` is the modern Compose-recommended base class.
- `AppCompatActivity` brings AppCompat themes, action-bar machinery, and a deeper view
  inflation pipeline that we don't use.
- The `LocaleManager` direct call is a one-liner that's identical in behavior on API 33+.

## Why we don't go fully manual (`createConfigurationContext` + `CompositionLocalProvider`)

Three previous PRs (#485, #487, #488, #499) tried to manually wrap `LocalContext` with a
locale-overridden `Configuration`. None propagated to `stringResource()` calls in practice.
The post-mortem at `docs/android/language-switching-postmortem.md` covers what was tried and
what we believe the failure modes were. Short version: the official platform API is the right
abstraction; we should let the system handle locale plumbing rather than reimplement it.

## Cold-start path

1. The platform reads its `LocaleManager` state at process start and applies the chosen
   locale to the Activity's `Configuration`. Resources resolve correctly from the first
   composition.
2. Independently, `ChatViewModel`'s constructor seeds `uiState.currentLocale` synchronously
   via `LanguagePreferences.readInitial()`. This guarantees the LLM `language` parameter is
   correct on the first chat request, even if the DataStore async load hasn't completed.

The two sources of truth (system `LocaleManager` and our `LanguagePreferences`) stay in sync
because `setLocale(...)` writes to both atomically.

## Activity-recreate cost

Calling `LocaleManager.setApplicationLocales(...)` triggers a single Activity recreate
(~150 ms visible flash). Two consequences worth knowing:

- An in-flight LLM streaming response is cancelled by the recreate. The picker lives in
  Settings, so a mid-conversation locale change is unusual; we don't currently buffer the
  in-flight stream across recreate.
- Conversation history reloads from Room on the new Activity instance — same path as device
  rotation cold-start, well-tested.

## Tested device matrix

| Device | OS | Result |
|---|---|---|
| Xiaomi (HyperOS V816) | Android 14 (API 34) | Works |
| CI emulator | Android 14 (API 34) | Builds; no UI test exercises the picker yet |

## Known limitation: API ≤32 path is unverified on `ComponentActivity`

The `AppCompatDelegate.setApplicationLocales` fallback for API 21–32 has the same
`AppCompatActivity`-required-for-init constraint that bit us on API 33+. We haven't tested it
on a pre-Android-13 device. Tracked as a follow-up — see the linked GitHub issue. If the
fallback turns out to be broken on API ≤32, the workaround is the same shape as the API 33+
fix: don't rely on `AppCompatDelegate`, persist the choice ourselves, and override
`attachBaseContext` on `MainActivity` to wrap the base context with a locale-aware
`Configuration` (synchronously, to avoid the persistence race that bit #485).

## Diagnostic logging

`LocaleApplier` emits `VoxLocale` Timber tags on every locale apply, including the SDK
version and the `LocaleManager` read-back after the set. Useful when triaging
device-specific issues. Read with:

```
adb logcat -d | grep VoxLocale
```

The logging is light enough to keep in production builds; it runs once per picker tap.
