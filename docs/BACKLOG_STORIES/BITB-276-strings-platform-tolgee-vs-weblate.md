---
id: BITB-276
status: todo
priority: P3
size: M
rank: 10
created: 2026-11-08
---

# BITB-276: Strings Platform — Evaluate Tolgee vs Weblate for the 3-Format Sync

**Migration note (2026-11-13, status):** gated: file when translation churn makes manual sync painful (the 11-locale, 3-client matrix is the trigger)
**Migration note (2026-11-13, size):** (evaluation)
**Follow-up to:** BITB-260 (its strings-sync candidate)

## User Story

**As the** maintainer, **I want** one tool syncing the 255-key × 11-locale string catalog across
`strings.xml`, next-intl `messages/*.json`, and (with iOS) `.xcstrings`, **so that** adding a key no
longer means hand-editing three formats in 11 languages.

## Evaluation candidates (survey [T-260B], 2026-11-07 — licenses verified)

| Platform | License | strings.xml | messages/*.json | .xcstrings | Status |
|---|---|---|---|---|---|
| **Tolgee** | Apache-2.0 core (EE separately licensed), self-hostable, active | ✅ | ✅ native JSON | ✅ `XcstringsFileProcessor` | **First candidate — all three formats** |
| Weblate | GPL-3.0; libre hosting for public projects | ✅ | ✅ | ❌ **not supported** (issue #10848, open since 2024) | Fallback — iOS needs converters |

## Requirements

1. Evaluate Tolgee first: self-host via docker-compose against the three real formats; check git sync
   round-trip fidelity (no key loss, no formatting churn).
2. Weblate only if Tolgee fails a hard requirement — record which (`.xcstrings` gap is the known one).
3. Non-goal: replacing the Android `translation-validation` CI job — the platform must be compatible
   with it or replace it wholesale with reasoning recorded.

**Acceptance Criteria:** decision record with a live round-trip demo on a branch, or a documented "keep
manual sync" verdict with the trigger condition re-evaluated.

**Related:** BITB-262 (registry's strings-catalog contract row), BITB-087 (iOS `.xcstrings`).
