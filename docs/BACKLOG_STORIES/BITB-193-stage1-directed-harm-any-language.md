# BITB-193: Stage-1 Directed-Harm Check Is Limited to the Detected Language

**Status:** 🎯 Todo
**Size:** S
**Created:** 2026-10-13

**As a** moderator of the chat, **I want** directed harm blocked in any language regardless of the detected language, **so that** mis-detected or non-Latin threats are not passed to the model.

## Problem

Found while implementing BITB-185. `MultiLanguageContentFilter.check_multilingual` selects
`self._directed_harm_regex.get(language) or self._directed_harm_regex.get("en")`. A French threat
detected as `en` skips the `fr` patterns, and ru/zh/hi/ko/ar have no directed-harm table so they only
get the English one. `_full_keyword_fallback` already uses `find_directed_harm` (all languages).

## Known cross-language false positives

`find_directed_harm` (used by the BITB-185 fallback) runs every language's directed-harm regex over
the text, so single-word patterns from one language fire on innocent text in another: it "Gioco
della morra", pt `\bmorra\b`, it `\bmuori\b`, fr `\bcrève\b`, es `\bmuérete\b`. Any change that
makes Stage 1 check all languages will inherit this; tighten those patterns (phrase-level, or
require a second-person target) as part of this story.

Related crisis-phrase false positive (found verifying BITB-185 v2): the pt crisis phrase "Quero que
eu morra" ("I want to die") is blocked as directed harm in the fallback because pt `\bmorra\b`
fires on it before the self-harm check. The same tightening fixes it; add it as a regression case.

## Acceptance criteria

- [ ] Stage 1 checks directed harm in every language (reuse `find_directed_harm`)
- [ ] Parametrized tests across the 11 language codes, including mismatched code/text
- [ ] Cross-language single-word false positives above no longer fire
- [ ] Decide whether ru/zh/hi/ko/ar directed-harm tables are needed (separate pattern work)
