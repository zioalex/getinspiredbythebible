# BITB-183: Self-Harm Keyword Fallback for Russian, Chinese, Hindi and Korean

**Status:** ✅ Done — PR #1148, 2026-10-11 (native-speaker review AC left open)
**Priority:** P2
**Size:** S
**Created:** 2026-10-10
**Prompted by:** BITB-182 follow-up — the gap was pinned by
`TestFollowUpCases::test_languages_without_keyword_patterns_are_documented` in
`api/tests/test_golden_set.py` (now flipped to `test_every_language_has_keyword_self_harm_patterns`).

**As a** user writing in Russian, Chinese, Hindi or Korean, **I want** a crisis message to
get the compassionate response even when ML moderation is down, **so that** I am not
treated like any ordinary Bible question.

## Bug Report

When the ML safety stage fails or is not configured (Llama Guard, OpenAI moderation or Azure),
`ContentSafetyService` falls back to `_full_keyword_fallback` (`api/utils/content_safety.py`). That
fallback detects possible help-seeking through `MultiLanguageContentFilter.SELF_HARM_PATTERNS`
(`api/utils/security.py`), which had patterns for en, it, de, es, fr, pt and ar only.

A direct crisis message in Russian, Chinese, Hindi or Korean (e.g. "я хочу покончить с собой",
"我想自杀", "मैं आत्महत्या करना चाहता हूँ", "죽고 싶어요") was therefore classified `clean (fallback)`: the
compassionate response path was not taken and follow-up chips were not suppressed.

## Functional Requirements

- FR1 Add `ru`, `zh`, `hi` and `ko` entries to `SELF_HARM_PATTERNS`, covering direct statements of
  suicidal intent and self-harm. Patterns for CJK must not rely on `\b` word boundaries.
- FR2 Keep the patterns narrow: questions *about* Scripture (Judas's death, Saul's death, Samson)
  must not trigger the compassionate path.

## Fix

Add ru, zh, hi, ko pattern lists. `\b` is used only for Russian; zh/hi/ko use plain
substrings (no word spaces in CJK, and `\b` is unreliable with Devanagari matras).
Patterns are phrase-level (`自杀`, `想死`, `不想活`, `자살`, `죽고 싶`, `목숨을 끊`,
`самоубийств`, `покончить с собой`, `хочу умереть`, `आत्महत्या`, `मरना चाहता`,
`खुद को नुकसान`), never a bare `死` / `죽`, with guards against common benign Bible-study
phrasings (`想死后`, `문자해석`, `혼자살`, `जान लेकर`) and Hindi nukta variants. Class docstring
updated to 11 languages.

## Acceptance Criteria

- [x] `_full_keyword_fallback` flags a direct crisis message in each of ru, zh, hi, ko
      (`allowed=True, compassionate_response_needed=True`)
- [x] Parametrized negative test: ordinary Bible / "death and resurrection" questions in all
      11 languages stay `clean`
- [x] Fullwidth punctuation (zh/ko), wrapped `( )` / `「」`, and embedded-in-sentence cases covered;
      `normalize_text` verified not to mangle these scripts; zero-width evasion still detected
- [x] The BITB-182 pin test is updated (the uncovered set becomes empty) and `crisis-keyword`
      cases for ru/zh/hi/ko are added to `api/golden_set/test_cases/follow_ups.yaml`
- [ ] Patterns reviewed by a native speaker or checked against a reference list per language

Tests: `api/tests/test_self_harm_keyword_fallback_languages.py`, `api/tests/test_golden_set.py`.

## Out of Scope

- Replacing the keyword fallback with an ML classifier (BITB-020 covers the ML stage).

## Follow-ups

- BITB-186 — crisis phrasings the first patterns miss (zh 我想跳楼, 活着没意思; ko 사라지고 싶어; ru Хочу сдохнуть, Мне незачем жить; hi मुझे मरना है) and
  first-person-negated false positives (ru 'Я не хочу умереть без покаяния').
- BITB-185 — the fallback only checks `[language, "en"]`, so short or mismatched-script messages
  detected as `en` skip the ru/zh/hi/ko/ar patterns; and violence is checked before self-harm, so
  fr "je veux me tuer" / pt "me matar" are blocked instead of getting the compassionate path.
