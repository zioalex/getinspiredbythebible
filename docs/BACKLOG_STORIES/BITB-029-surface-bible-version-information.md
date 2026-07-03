# BITB-029: Surface Bible Version Information More Clearly

**Status:** ✅ Done — amber chip badge in top header bar (web); backend prompt guidance already wired (`BIBLE_VERSION_GUIDANCE`).

## User Story

As a user reading AI responses, I want the currently selected Bible version to be clearly visible and easy to open, so that I can trust the translation context behind quoted verses.

## Problem

Bible version information exists but is not surfaced strongly enough during normal chat usage. Users who care about translation fidelity may ask "Which Bible version is this?" in chat because the version source is not obvious at the point of reading responses.

When that happens, the assistant should not provide vague or conflicting wording. It should direct users back to the dedicated Bible version information surface, which is the single source of truth for active translation details.

## Proposed Changes

### 1. Increase visibility of active Bible version

- Surface the active Bible version in a prominent and persistent location in the chat UI (web and Android), close to where verses are read.
- Ensure the label remains clear in both light and dark themes and across supported locales.

### 2. Add clear navigation to version details

- Make the visible version indicator interactive so users can open the existing Bible version information surface in one tap/click.
- Reuse existing version information UI instead of creating a second source of truth.

### 3. Guide assistant responses when users ask about version

- Update response guidance so that when users ask which version is being used, the assistant points them back to the Bible version information location.
- Keep wording concise, consistent, and localizable.

## Acceptance Criteria

- [ ] Active Bible version is visibly displayed in the primary chat experience on web.
- [ ] Active Bible version is visibly displayed in the primary chat experience on Android.
- [ ] Version indicator opens/navigates to the existing Bible version information surface.
- [ ] If user asks about Bible version in chat, assistant points to Bible version information instead of improvising version details.
- [ ] Behavior works in all currently supported UI locales without fallback regressions.
- [ ] Existing translation selection/persistence behavior remains unchanged.

## Files to Modify

| File | Change |
|---|---|
| `frontend/src/app/[locale]/page.tsx` (or related chat header component) | Add more prominent Bible version indicator + interaction hook |
| `frontend/messages/*.json` | Add/update localized copy for version indicator and assistant guidance text if needed |
| `android/app/src/main/kotlin/.../ChatScreen.kt` (or equivalent top-bar composable) | Surface active Bible version prominently and make it discoverable |
| `api/chat/prompts/*` (or response policy location) | Add guidance for "version asked" behavior to point users to version info |

## Out of Scope

- Changing which Bible translation is selected by default.
- Adding new translation providers.
- Reworking scripture retrieval, citation parsing, or ranking logic.

## Priority

P2 – Medium (trust/clarity improvement with user-facing UX impact)

## Size

S (< 4 hours)

## Assignee

fullstack-expert
