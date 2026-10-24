# BITB-237: Native Directed-Harm Patterns for ar/ru/zh/hi/ko

**Status:** 🎯 Todo
**Priority:** P3
**Size:** M
**Created:** 2026-10-24

## Problem

Follow-up to BITB-193. Stage 1 (`MultiLanguageContentFilter.check_multilingual`) now checks the
directed-harm table of every language, but `DIRECTED_HARM_PATTERNS` only has en/it/de/es/fr/pt. A
native-script threat in ar/ru/zh/hi/ko (for example "убей себя", "去死", "मर जाओ", "죽어", "اقتل نفسك")
passes Stage 1 and relies on Stage 2 moderation alone; with ML moderation down the keyword fallback
does not catch it either.

## Acceptance criteria

- [ ] Conservative directed-harm tables for ar, ru, zh, hi and ko (second-person target or clause-anchored imperative)
- [ ] Native-script threats blocked under all 11 UI language codes (mismatched code/text)
- [ ] Self-harm first-person phrasings and Bible-narrative questions stay unblocked (cf. BITB-186 / BITB-198 benign sets)
- [ ] Parametrized across the 11 languages; guard test updated
