# BITB-175: Localized What's New / Changelog Entries (Web + Android)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** M
**Created:** 2026-10-04
**Prompted by:** BITB-119 verification — the What's New surfaces only show English text.

## User Story

**As** a user who runs Vox Quieta in Italian, German, Arabic, Hindi or any of the other ten
non-English locales, **I want** the "What's New" sheet to describe new features in my language,
**so that** I actually understand what changed.

## Problem

Both What's New surfaces (web `WhatsNewModal.tsx`, Android `WhatsNewBottomSheet.kt`) read a
`changelog.json` that `frontend/scripts/extract-latest-changelog.mjs` and the Android asset build
derive from `CHANGELOG.md`. release-please writes that file in English from conventional-commit
subjects, so every locale sees English text (first observed for BITB-119 "Read the answer aloud").

## Acceptance Criteria

- [ ] A localized release-notes source exists for all 11 locales (en, it, de, es, fr, pt, ar, ru,
      zh, hi, ko), keyed by release version
- [ ] Web and Android What's New show the entry for the current UI locale and fall back to English
      when a translation is missing
- [ ] The release flow documents how localized notes are added (`docs/RELEASE_PROCESS.md`) without
      breaking release-please
- [ ] Tests on both platforms cover locale selection and the English fallback
