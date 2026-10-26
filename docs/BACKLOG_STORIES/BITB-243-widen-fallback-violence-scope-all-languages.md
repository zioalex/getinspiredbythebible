# BITB-243: Widen Keyword-Fallback Violence Scope to Every Language

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-26

## Problem

Follow-up to BITB-194 (optional). Step (e) of `_full_keyword_fallback` checks the detected UI
language, English and the unique-script languages (ru/zh/hi/ko). A user whose UI is, say, `en`
but who writes Spanish or Arabic gets no violence check in the fallback. Now that the Latin/Arabic
tables are intent-gated (BITB-194), the old reason for excluding `ar` (bare `قتل` false positives)
is gone, so scope could be widened to every language.

## Acceptance criteria

- [ ] Evaluate false-positive risk across the 11 languages (cross-language narrative corpus)
- [ ] If acceptable, step (e) checks all languages incl. `ar`; tests assert each language's intent block under every UI code
- [ ] Update the `_UNIQUE_SCRIPT_VIOLENCE_LANGS` comment accordingly
