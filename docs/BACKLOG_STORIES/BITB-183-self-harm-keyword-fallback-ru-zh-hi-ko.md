# BITB-183: Self-Harm Keyword Fallback for Russian, Chinese, Hindi and Korean

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-10
**Prompted by:** BITB-182 follow-up — the gap is pinned by
`TestFollowUpCases::test_languages_without_keyword_patterns_are_documented` in
`api/tests/test_golden_set.py`.

## Bug Report

When the ML safety stage fails or is not configured (Llama Guard, OpenAI moderation or Azure),
`ContentSafetyService` falls back to `_full_keyword_fallback` (`api/utils/content_safety.py`). That
fallback detects possible help-seeking through `MultiLanguageContentFilter.SELF_HARM_PATTERNS`
(`api/utils/security.py`), which has patterns for en, it, de, es, fr, pt and ar only.

A direct crisis message in Russian, Chinese, Hindi or Korean (e.g. "я хочу покончить с собой",
"我想自杀", "मैं आत्महत्या करना चाहता हूँ", "죽고 싶어요") is therefore classified `clean (fallback)`: the
compassionate response path is not taken and follow-up chips are not suppressed.

## Functional Requirements

- FR1 Add `ru`, `zh`, `hi` and `ko` entries to `SELF_HARM_PATTERNS`, covering direct statements of
  suicidal intent and self-harm. Patterns for CJK must not rely on `\b` word boundaries.
- FR2 Keep the patterns narrow: questions *about* Scripture (Judas's death, Saul's death, Samson)
  must not trigger the compassionate path.

## Acceptance Criteria

- [ ] `_full_keyword_fallback` flags a direct crisis message in each of ru, zh, hi, ko
- [ ] Parametrized negative test: ordinary Bible questions in all 11 languages stay `clean`
- [ ] The BITB-182 pin test is updated (the uncovered set becomes empty) and `crisis-keyword`
      cases for ru/zh/hi/ko are added to `api/golden_set/test_cases/follow_ups.yaml`
- [ ] Patterns reviewed by a native speaker or checked against a reference list per language

## Out of Scope

- Replacing the keyword fallback with an ML classifier (BITB-020 covers the ML stage).
