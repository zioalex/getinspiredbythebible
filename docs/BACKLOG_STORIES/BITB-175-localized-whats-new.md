---
id: BITB-175
status: todo
priority: P3
kind: feature
size: M
created: 2026-10-04
depends_on: [BITB-367]
---

# BITB-175: Localized What's New / Changelog Entries (Web + Android)

**Prompted by:** BITB-119 verification — the What's New surfaces only show English text.

**Scope added 2026-11-26 (BITB-368):** this story is the end-user layer of the product-release
work (BITB-366..368). Besides being localized, the entries are curated: 3–5 plain-language bullets
per release, features and user-visible fixes only, never the raw developer CHANGELOG (today the
popup shows `opencode`/`kubeopencode` entries and BITB ids). Source: one file per release and
locale, drafted from the milestone's `feature`/`fix` stories by `release_notes.py --user`; no
popup when a release has none. The same text feeds the Play Store "What's new".

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
