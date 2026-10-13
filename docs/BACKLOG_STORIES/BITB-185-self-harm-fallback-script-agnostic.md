# BITB-185: Self-Harm Fallback — Script-Agnostic Matching and Precedence

**Status:** In Review (PR pending)
**Size:** S
**Created:** 2026-10-10

**As a** user in crisis, **I want** the keyword fallback to recognise my message regardless
of detected language or phrasing, **so that** I get the compassionate response.

## Problem

Found while verifying BITB-183 (`ContentSafetyService._full_keyword_fallback`):

1. It only checks `[language, "en"]`. Short or mismatched-script messages whose language is
   detected as `en` skip the ru/zh/hi/ko/ar self-harm patterns.
2. Violence patterns run before self-harm, so fr "je veux me tuer" and pt "me matar" are
   blocked as violence instead of taking the compassionate path.

## Acceptance criteria

- [x] The fallback runs every language's self-harm regex, independent of the detected language
- [x] First-person self-harm phrases take precedence over violence matches (directed harm still blocks)
- [x] Parametrized tests across all 11 languages, including mismatched language/script cases

## Implementation notes

- `MultiLanguageContentFilter.find_self_harm(normalized, preferred=None)` tries the detected
  language first, then every other language's self-harm regex; returns `(language, matched_text)`.
  `find_directed_harm(normalized)` checks every language's directed-harm regex plus hate speech.
  Pattern tables and `check_multilingual` are unchanged (pattern gaps stay with BITB-186).
- `_full_keyword_fallback` order is now: (a) directed harm / hate speech in any language -> block
  (`keyword_violation:directed_harm (fallback)` / `:hate_speech (fallback)`); (b) self-harm in any
  language -> compassionate result (logs `matched_language`); (c) violence scoped to
  `[language, "en"]` -> block; (d) clean.
- Self-harm now wins over plain violence keywords ("I want to kill myself with a gun" is
  compassionate). Trade-off: a mixed "kill him then myself" message without directed-harm phrasing
  is treated as help-seeking (decision tracked in BITB-195).
- Exception to self-harm-first: when the only self-harm match is a bare noun (suicide, suicidio,
  suicídio, Selbstmord, Suizid; `_BARE_SELF_HARM_TERM`) AND a violence keyword matches, violence
  wins and the message is blocked ("how do I make a suicide bomb"). First-person phrases and bare
  "I am thinking about suicide" stay compassionate. Regression tests cover en/fr/es/it/pt.
- Known limitation: `find_directed_harm` runs every language's directed-harm regex, so single
  words from other languages give false positives in the fallback (it "Gioco della morra", pt
  `\bmorra\b`, it `\bmuori\b`, fr `\bcrève\b`, es `\bmuérete\b`). Documented, not fixed
  (see BITB-193).
- Tests: `api/tests/test_self_harm_keyword_fallback_languages.py` gains first-person overlap,
  11-language x phrase cross-products (crisis and benign), 15 mismatched language/script cases,
  directed harm x 11 codes, plain violence, and three end-to-end `check()` tests with ML moderation
  down.

## Follow-ups

- BITB-193: stage-1 `check_multilingual` directed-harm check limited to the detected language
- BITB-194: fallback violence regex blocks Bible-narrative questions when ML moderation is down
- BITB-195: decision on mixed self-harm + third-party violence messages
