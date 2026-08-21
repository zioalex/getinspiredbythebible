# BITB-082: Android — About Settings Row + First-Run Intro Fold-In

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S (~1 day)
**Created:** 2026-07-27
**Source:** Deferred scope — both BITB-076 and BITB-077 explicitly excluded Android and pointed
here rather than widening their own stories.

## User Story

**As an** Android user, **I want** to read who built Vox Quieta and why, from Settings, **so
that** I have the same "why does this exist" answer web visitors get from `/about`.

**As an** Android user opening the app for the first time after this ships, **I want** a short
one-time note about why Vox Quieta exists, **so that** I get the same one-time announcement web
users get, without a fifth first-run interruption competing for my attention.

## Why

BITB-076 shipped `/about` on the web; nothing on Android answers the same question. BITB-077's
web intro modal was scoped to web only because Android already has enough first-run machinery —
its own [`SplashScreen.kt`](../../android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/SplashScreen.kt),
the "What's New" bottom sheet (**BITB-058**, shipped), and a first-run feature spotlight
(**BITB-054**) — and adding a fourth interruption wasn't this story's call to make.

**Correction while scoping this:** BITB-054 (the spotlight) is still `Status: 🎯 Todo` — it has
not been built. "Fold into BITB-054" is not available today. The only real fold-in point that
exists right now is the What's New sheet, and that comes with a genuine collision to solve (see
below). If BITB-054 ships first, revisit whether the spotlight is a better home for this message.

## Part A — Settings → About row

Android's Settings screen already has a `settings_about_title` section
(`SettingsScreen.kt:174-224`) with a version row and `TextButton`s that open the Privacy Policy
and Terms of Service via `ACTION_VIEW` — both locale-aware, built from `LegalUrls.kt`:

```kotlin
fun privacyUrl(languageCode: String, base: String = BuildConfig.FRONTEND_URL): String =
    "${frontendBase(base)}/${webLocaleFor(languageCode)}/privacy"
```

Add the third row the same way — no native content duplication, no new screen:

- `LegalUrls.kt`: add `fun aboutUrl(languageCode: String, base: String = BuildConfig.FRONTEND_URL) = "${frontendBase(base)}/${webLocaleFor(languageCode)}/about"`.
- `SettingsScreen.kt`: add a `TextButton` in the About section (before or after the Privacy
  Policy row, ~line 201-212) reading `settings_about_link`, opening
  `aboutUrl(currentLanguage)` via the same `Intent(Intent.ACTION_VIEW, Uri.parse(...))` pattern
  already used for Privacy/Terms.

This is the cheap, consistent option: Privacy and Terms are already external links, not native
screens, so About following the same pattern needs no new screen, no content duplication between
platforms, and no extra translation surface for the full essay (only a one-line menu label).

## Part B — First-run intro fold-in

Reuse the **splash-cookie pattern**, not the What's-New version-int pattern — BITB-077 already
established that the right semantics for this message are "seen ever" (boolean), not "seen this
version" (int), because it's a one-time announcement, not a per-release changelog.

Mirror `hasSplashBeenSeen()` / `markSplashSeen()` (`MainActivity.kt:51-57`) with a parallel flag
in the same `app_prefs` SharedPreferences file:

```kotlin
private fun Context.hasAboutIntroBeenSeen(): Boolean =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getBoolean("about_intro_seen", false)

private fun Context.markAboutIntroSeen() =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putBoolean("about_intro_seen", true).apply()
```

Compute `showAboutIntroOnLaunch` in `onCreate()` alongside the existing
`showWhatsNewOnLaunch` (`MainActivity.kt:89`, `113-122`), and render a new
`AboutIntroBottomSheet` (modeled on `WhatsNewBottomSheet.kt`) in the same `Box` where
`WhatsNewBottomSheet` is rendered today (`MainActivity.kt:260-270`).

### The collision this creates — and the fix

`WhatsNewBottomSheet`'s version is marked seen **unconditionally** at `MainActivity.kt:121`
(`markVersionSeen(BuildConfig.VERSION_CODE)`), regardless of whether the sheet actually renders.
If the About intro is also eligible on the same cold start, showing both stacked is out (same
"never compete for one page load" rule BITB-077 applied on web), and the web precedent is
**intro wins, What's New defers to the next launch** — not "mark it seen anyway."

That means line 121's unconditional mark must become conditional:

```kotlin
val storedVersion = lastSeenVersionCode()
showWhatsNewOnLaunch = shouldShowWhatsNew(storedVersion, BuildConfig.VERSION_CODE)
showAboutIntroOnLaunch = !context.hasAboutIntroBeenSeen()

if (showAboutIntroOnLaunch) {
    // Intro modal owns this cold start. Don't mark the version seen — What's New
    // re-evaluates (and can show) on the very next launch.
    showWhatsNewOnLaunch = false
} else if (storedVersion != BuildConfig.VERSION_CODE) {
    markVersionSeen(BuildConfig.VERSION_CODE)
}
```

Mark `about_intro_seen` on dismiss (or on the sheet's primary/secondary action), not
preemptively — a process death before the user acts should still show it next launch, same
reasoning the existing `markVersionSeen` comment (`MainActivity.kt:117-118`) already gives for
*not* doing this on What's New, which this story is intentionally diverging from for the reason
above.

## Acceptance Criteria

- [ ] Settings → About has a third row linking to `voxquieta.org/{locale}/about` in the device's
      current app language, opened via `ACTION_VIEW` (same pattern as Privacy/Terms).
- [ ] On first cold start after this ships, every user sees the About intro sheet once.
- [ ] Dismissing it (primary action, secondary action, or system back) persists — it never
      reappears for that install.
- [ ] The About intro sheet and the What's New sheet never render on the same cold start; if
      both are eligible, About intro shows and What's New re-evaluates on the next launch
      (its version is *not* marked seen on the deferred run).
- [ ] Neither sheet renders stacked on the system splash screen.
- [ ] All new strings (`about_intro_title`, `about_intro_body`, `about_intro_primary_cta`,
      `about_intro_secondary_cta`, `settings_about_link`) present in `values/strings.xml` and all
      11 `values-*/strings.xml` locales, sourced from the same condensed copy as the web
      `About.intro*` keys (not re-derived independently).
- [ ] `about_intro_body` stays close to the web's ~60-word target — same "gentle companion, not a
      replacement for therapy or pastoral care" sentence survives the edit down (see BITB-076's
      *Source Material* section for the exact line).

## Tests to Add

- Unit test for the version/seen interaction, mirroring `WhatsNewTest.kt`
  (`android/app/src/test/kotlin/org/voxquieta/app/screens/WhatsNewTest.kt`): given
  `about_intro_seen == false` and a `storedVersion` that would normally trigger What's New,
  assert What's New is suppressed this run and the version is *not* marked seen.
  `android/app/src/test/kotlin/org/voxquieta/app/screens/AboutIntroTest.kt` (new).
- Compose UI test on `SettingsScreen`: About section renders the new row; clicking it fires an
  `ACTION_VIEW` intent to the expected locale-aware URL.
- Compose UI test on `AboutIntroBottomSheet`: renders when `about_intro_seen == false`; dismiss
  actions call the seen-marking callback.

## Files Likely to Change

| File | Change |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/utils/LegalUrls.kt` | Add `aboutUrl()` |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/SettingsScreen.kt` | New About-section row (~line 201-212) |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/AboutIntroBottomSheet.kt` | **New** — modeled on `WhatsNewBottomSheet.kt` |
| `android/app/src/main/kotlin/org/voxquieta/app/MainActivity.kt` | `hasAboutIntroBeenSeen()`/`markAboutIntroSeen()` helpers; compute `showAboutIntroOnLaunch`; make the What's New version-seen write conditional (~lines 51-57, 89, 113-122, 260-270) |
| `android/app/src/main/res/values*/strings.xml` (12: default + 11 locales) | New keys listed above |
| `android/app/src/test/kotlin/org/voxquieta/app/screens/AboutIntroTest.kt` | **New** |

## Out of Scope

- A native, in-app rendering of the full About essay. Settings links out to the web page, same
  as Privacy/Terms — one canonical copy of the long-form content, not two to keep in sync.
- Folding this into the BITB-054 spotlight tour — that story hasn't shipped yet. Revisit if it
  lands first.
- Re-deriving the intro copy independently. It must trace back to the same web `About.intro*`
  source (BITB-077), just as that traces back to the ai4you.sh origin post (BITB-076) — not a
  fresh LLM paraphrase on Android.

## Related

- **BITB-076** — the web `/about` page this story links out to; the canonical copy source.
- **BITB-077** — the web intro modal; this story is its Android counterpart and reuses its
  "seen-once" (not "seen-per-version") reasoning.
- **BITB-058** — Android What's New bottom sheet; the collision this story resolves.
- **BITB-054** — Android first-run spotlight; still `Todo`, a possible future fold-in target.
