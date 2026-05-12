# BITB-031: Android Settings — "What's New" / Changelog Screen

## User Story

As an Android user, I want to see a "What's New" / Changelog section in the
Settings screen, so I can discover what changed in each release without
leaving the app and without having to visit the website.

## Problem

The Android app has no in-app surface for release notes. The web frontend
already exposes a changelog page at `/[locale]/changelog`, backed by
`frontend/public/changelog.json` and `frontend/public/CHANGELOG.md` (both
generated at build time from the repo-root `CHANGELOG.md` by
`frontend/scripts/extract-latest-changelog.mjs`). Mobile users are left
without that visibility.

The repo-root `CHANGELOG.md` is the canonical source — it's
release-please-managed, updated on every release, and already structured by
version. Bundling a **pre-parsed JSON** derivation of it into the APK keeps
the Android changelog automatically in sync with releases (no separate
hand-maintained list), works offline, and avoids shipping a Markdown
renderer on Android just to display release notes.

## Approach: pre-bundled JSON asset

Generate a `changelog.json` file at build time that contains **all**
release entries (not just the latest, which is what
`frontend/public/changelog.json` already holds — that single-entry artifact
is intentional for the frontend's "What's New" modal). The Android module
will read this JSON from `assets/` and render it as native Compose UI.

Shape:

```json
[
  { "version": "0.8.0", "date": "2026-05-08", "body": "### Features\n- …\n" },
  { "version": "0.7.0", "date": "2026-04-22", "body": "…" }
]
```

The `body` stays as Markdown text — the v1 Android screen renders it as
plain text. No new Markdown dependency required.

## Proposed Changes

### 1. Add a "What's New" entry to the About section in Settings

Inside `SettingsScreen.kt` the About section currently lists Version,
Privacy Policy, and Terms of Service (lines 190–241). Add a third
`TextButton` after Terms of Service that navigates to a new
`ChangelogScreen`. Keep it grouped with About — it's reference info, not a
preference.

### 2. Generate the pre-bundled `changelog.json` asset at build time

Mirror the pattern in `frontend/scripts/extract-latest-changelog.mjs`, but
emit **all** entries. Recommended split of work:

- **Generalize the existing script** (or add a sibling
  `scripts/extract-all-changelog.mjs` at the repo root) that reuses the
  same `parseLatestEntry` regex in a loop, walking every `^## ` heading
  in `CHANGELOG.md` and emitting an array. Keep the parser logic shared
  so it stays in sync with release-please's heading format.
- **Add a Gradle task** to the Android module's build script that:
  - Runs the Node script (or, simpler, parses the markdown directly in
    Gradle/Kotlin if you want to avoid a Node dependency in the Android
    build — see "Alternative" below).
  - Writes the JSON to `android/app/src/main/assets/changelog.json`
    before the Android `preBuild` task runs.
  - Makes `preBuild` depend on the new task so the asset is always
    fresh.
  - **Fails soft**: if the source `CHANGELOG.md` is missing (e.g. someone
    checking out only the `android/` subtree), write
    `{ "entries": [] }` and continue — the screen shows its empty-state
    fallback.

> **Recommended path**: do the parse in pure Gradle/Kotlin so the Android
> build doesn't require Node. The grammar is simple enough (single regex)
> that this is a few dozen lines.
>
> **Alternative path**: shell out to `node frontend/scripts/extract-all-changelog.mjs`
> from a Gradle `Exec` task. Reuses the parser; adds a Node toolchain
> requirement to Android builds.

> Implementer note: verify the actual module build script path. Likely
> `android/app/build.gradle.kts`; could be `build.gradle` if the module
> hasn't been migrated to KTS.

### 3. New `ChangelogScreen.kt`

- Location:
  `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/ChangelogScreen.kt`.
- Reads the asset via `context.assets.open("changelog.json")`. Wrap the
  read in a try/catch — return an empty list if the asset is missing or
  unparseable.
- Deserialize with `kotlinx.serialization` into a
  `List<ChangelogEntry>` where
  `data class ChangelogEntry(val version: String, val date: String?, val body: String)`.
- Renders the entries in a `LazyColumn`. Each card shows version + date as
  a header and the body below.

**v1 rendering — recommended:** render `body` as plain text in
`Text(style = MaterialTheme.typography.bodyMedium)`. The body is short
Markdown (mostly bullet lists) — readable as plain text. No new dependency.

Alternative: pull in a lightweight Compose Markdown renderer
(e.g. `compose-markdown`) for richer formatting. Defer unless v1 reads
poorly in QA.

### 4. Navigation wiring

`SettingsScreen` already accepts `onNavigateBack: () -> Unit`. Add a sibling
parameter `onNavigateToChangelog: () -> Unit`, pass it down from wherever
`SettingsScreen` is composed, and register the new route in the navigation
graph. Implementer should locate the nav graph — likely in
`MainActivity.kt` or `android/app/src/main/kotlin/org/voxquieta/app/presentation/navigation/` (verify path).

### 5. String resources

Add to `android/app/src/main/res/values/strings.xml` and to all 10 locale
variants (`values-de`, `values-ru`, `values-zh`, `values-hi`, `values-ar`,
`values-pt`, `values-ko`, `values-fr`, `values-it`, `values-es`):

- `settings_changelog_title` — title of the screen (e.g. "What's New")
- `settings_changelog_link` — label of the Settings entry (e.g. "What's New")
- `changelog_empty` — fallback shown when the asset is missing/empty
  (e.g. "Release notes are not available right now.")

The changelog body itself stays in English (it's release-managed and
auto-generated), matching the frontend's behaviour.

## Acceptance Criteria

- [ ] Settings shows a "What's New" entry in the About section that opens a
      new screen.
- [ ] The Changelog screen lists every release present in the repo-root
      `CHANGELOG.md`, rendered from the bundled `changelog.json` asset.
- [ ] When `changelog.json` is missing or empty, the screen shows the
      `changelog_empty` fallback instead of crashing.
- [ ] The Gradle task runs automatically before `preBuild` — running
      `./gradlew clean assembleDebug` produces an APK that contains a
      non-empty `assets/changelog.json` matching the repo-root markdown.
- [ ] All 11 locales (English + 10 variants) have translated values for the
      new strings.
- [ ] `./gradlew assembleDebug` succeeds.
- [ ] Manual QA: open Settings → tap "What's New" → verify recent releases
      (0.8.0, 0.7.0, …) are visible and readable.

## Files to Modify

| File | Change |
|---|---|
| `android/app/build.gradle.kts` (verify path) | Add Gradle task to parse repo-root `CHANGELOG.md` into `src/main/assets/changelog.json`; wire it as a `preBuild` dependency |
| `frontend/scripts/extract-latest-changelog.mjs` *(optional)* | If reusing the Node parser: extract `parseAllEntries` so it can be shared between frontend single-entry output and Android all-entries output |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/SettingsScreen.kt` | Add `onNavigateToChangelog` parameter; add "What's New" `TextButton` in the About section |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/ChangelogScreen.kt` | New file — load asset, parse, render |
| Navigation graph (e.g. `MainActivity.kt` or `presentation/navigation/*.kt`) | Register the new route and wire `onNavigateToChangelog` |
| `android/app/src/main/res/values/strings.xml` + 10 locale variants | Add `settings_changelog_title`, `settings_changelog_link`, `changelog_empty` |
| `.gitignore` (verify) | If `assets/CHANGELOG.md` is generated, optionally ignore it so the bundled copy isn't checked in |

## Out of Scope

- Markdown fidelity beyond headings + paragraphs (no syntax highlighting,
  no clickable PR links).
- Translation of the changelog body — body stays in English, mirroring the
  frontend.
- Fetching the changelog from GitHub at runtime.
- A "What's New" modal on app start after an upgrade (separate story).
- iOS app.

## Priority

P2 — Medium. Improves discoverability of new features; no broken
functionality today.

## Size

M (4–8 hours) — build-script glue + a new screen + nav wiring + 11 string
resource files.

## Dependencies / Related Work

- Frontend equivalent: PR #474 (`feat(frontend): add changelog page and
  what's-new modal`).
- Prior-art script: `frontend/scripts/extract-latest-changelog.mjs`.
- Builds on: BITB-026 (settings UX improvements).

## Assignee

android-expert
