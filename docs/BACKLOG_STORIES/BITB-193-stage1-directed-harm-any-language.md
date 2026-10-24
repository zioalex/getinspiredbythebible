# BITB-193: Stage-1 Directed-Harm Check Is Limited to the Detected Language

**Status:** 🔍 In Review
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

- [x] Stage 1 checks directed harm in every language (`find_directed_harm_violation`)
- [x] Parametrized tests across the 11 language codes, including mismatched code/text
- [x] Cross-language single-word false positives above no longer fire
- [x] Decide whether ru/zh/hi/ko/ar directed-harm tables are needed (separate pattern work) — yes, filed as BITB-237

## Decision

Directed harm is checked in every language regardless of the detected/selected language; the
detected language only sets which table is tried first. Native ar/ru/zh/hi/ko tables are out of scope
and tracked in BITB-237. Single-word imperatives are anchored rather than removed, so real threats
("Muori!", "Crève, connard") still block.

## Implementation

- `api/utils/security.py`: new `MultiLanguageContentFilter.find_directed_harm_violation(normalized,
  preferred=None)` returning `(violation_type, language, matched_text)` (directed harm of every
  language, preferred first, then hate speech with language `"all"`). `find_directed_harm` is now a
  thin wrapper; `check_multilingual` uses it and logs `matched_language`.
- `DIRECTED_HARM_PATTERNS` tightened with `_DH_START` / `_DH_END` clause anchors (it `muori`, fr
  `crève`, pt `morra`), insult-follow forms, `spero che tu muoia`, `va crever`, `que tu crèves`,
  `que você/tu morra`, and an es `muérete de <risa|envidia|...>` negative lookahead.
- `SELF_HARM_PATTERNS["pt"]` gains `quero que eu morra`, so it is compassionate, not clean/blocked.
- `api/utils/content_safety.py`: `_full_keyword_fallback` uses `find_directed_harm_violation` (no
  private regex access); docstrings say "any language".

## Tests

- New `api/tests/test_stage1_directed_harm_any_language.py`: directed texts x 11 codes, hate speech x
  11 codes, false-positive list x 11 codes (Stage 1, `find_directed_harm`, fallback), benign Bible
  questions in all 11 languages, pt "Quero que eu morra" compassionate path, service
  `_check_stage1_keywords` for en/ar/ru/zh/hi/ko, tuple unit tests, table-keys guard.
- `api/tests/test_self_harm_keyword_fallback_languages.py`: `("pt", "Quero que eu morra")` added to CRISIS.

## Known limitations

- Mid-sentence bare imperatives ("adesso muori", "e ora crève") are not matched by the anchored
  patterns; they are left to Stage 2 ML moderation.
- ar/ru/zh/hi/ko have no native directed-harm table (BITB-237).

## Follow-ups

- BITB-237: native directed-harm patterns for ar/ru/zh/hi/ko.
- BITB-235: English "kill yourself" help-seeking/theological questions blocked under every code.
- BITB-236: directed-harm recall lost by the tightening (it/fr/pt).
