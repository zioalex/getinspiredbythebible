# BITB-179: Keyword Self-Harm Fallback Missing ru, zh, hi, ko

**Status:** In review
**Size:** S
**Created:** 2026-10-10

**As a** user writing in Russian, Chinese, Hindi or Korean, **I want** a crisis message to
get the compassionate response even when ML moderation is down, **so that** I am not
treated like any ordinary Bible question.

## Problem

`MultiLanguageContentFilter.SELF_HARM_PATTERNS` (`api/utils/security.py`) only had
en, it, de, es, fr, pt, ar. `ContentSafetyService._full_keyword_fallback`
(`api/utils/content_safety.py`) therefore never flagged ru/zh/hi/ko crisis messages when
OpenAI Moderation / Llama Guard were unavailable.

## Fix

Add ru, zh, hi, ko pattern lists. `\b` is used only for Russian; zh/hi/ko use plain
substrings (no word spaces in CJK, and `\b` is unreliable with Devanagari matras).
Patterns are phrase-level (`自杀`, `想死`, `不想活`, `자살`, `죽고 싶`, `목숨을 끊`,
`самоубийств`, `покончить с собой`, `хочу умереть`, `आत्महत्या`, `मरना चाहता`,
`खुद को नुकसान`), never a bare `死` / `죽`. Class docstring updated to 11 languages.

## Acceptance criteria

- ru/zh/hi/ko crisis phrases return `allowed=True, compassionate_response_needed=True` from the fallback
- Benign "death and resurrection" Bible questions in all 11 languages do not trigger
- Fullwidth punctuation (zh/ko), wrapped `( )` / `「」`, and embedded-in-sentence cases covered
- `normalize_text` verified not to mangle these scripts; zero-width evasion still detected
- Tests: `api/tests/test_self_harm_keyword_fallback_languages.py`

## Out of scope / known

- For fr/pt, violence patterns run first in the fallback, so e.g. "je veux me tuer" /
  "me matar" is blocked as violence rather than treated as help-seeking (pre-existing).
