# BITB-180: Self-Harm Fallback — Script-Agnostic Matching and Precedence

**Status:** Todo
**Size:** S
**Created:** 2026-10-10

**As a** user in crisis, **I want** the keyword fallback to recognise my message regardless
of detected language or phrasing, **so that** I get the compassionate response.

## Problem

Found while verifying BITB-179 (`ContentSafetyService._full_keyword_fallback`):

1. It only checks `[language, "en"]`. Short or mismatched-script messages whose language is
   detected as `en` skip the ru/zh/hi/ko/ar self-harm patterns.
2. Violence patterns run before self-harm, so fr "je veux me tuer" and pt "me matar" are
   blocked as violence instead of taking the compassionate path.

## Acceptance criteria

- The fallback runs every language's self-harm regex, independent of the detected language
- First-person self-harm phrases take precedence over violence matches (directed harm still blocks)
- Parametrized tests across all 11 languages, including mismatched language/script cases
