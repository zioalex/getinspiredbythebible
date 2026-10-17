# BITB-198: Keyword Fallback Has No Native Violence Patterns for ru/zh/hi/ko

**Status:** 🔍 In Review
**Size:** M
**Created:** 2026-10-13

## Problem

Follow-up to BITB-185 v2 (pre-existing at main): `VIOLENCE_PATTERNS` has no ru, zh, hi or ko entries, so plain violence (no self-harm) in those languages is clean in the fallback when ML moderation is down. BITB-185 v2 added a separate `HARD_VIOLENCE_PATTERNS` table (bombs, terror, massacre) used only next to self-harm; the general violence table was deliberately not edited.

## Acceptance criteria

- [x] Native violence patterns for ru, zh, hi, ko with Bible-narrative false-positive review (see BITB-194)
- [x] Parametrized tests across all 11 languages incl. CJK/fullwidth and Devanagari
- [x] Hard-violence table reconciled with the violence table

## Note (from BITB-185 v2 verification)

ru verb `напасть` (to attack) is not covered by the ru hard-violence table (`нападен` only).

## Plan / implementation (2026-10-17)

- `VIOLENCE_PATTERNS` gains ru, zh, hi, ko (`api/utils/security.py`, after "ar"), **narrative-safe**
  per the BITB-194 design principle: Bible questions are full of killing (David/Goliath, Cain/Abel,
  Saul wanting to kill David), Herod's massacre, Philistine attacks, "weapons of our warfare" and
  "thou shalt not murder". So these four languages deliberately do NOT match bare
  kill/murder/attack/massacre/weapon words. They match only: explosives/terror terms, firearm nouns
  (pistol, rifle, gun), and first-person or how-to intent phrasings ("хочу убить его", "我要杀了他",
  "मैं उसे मार डालूँगा", "그 사람을 죽이고 싶어"). Third-person narrative ("사울은 왜 다윗을 죽이고 싶어
  했나요?") is excluded by lookaheads. Hindi uses explicit Devanagari look-arounds instead of `\b`.
- Reconciliation: documented rule above `HARD_VIOLENCE_PATTERNS`. For ru, the hard table gains only
  `\bнапасть на\b` and `\bнападу на\b` next to the existing `нападен`; bare `напал(а|и)` /
  `нападает` are NOT matched, so idioms like "на меня напала тоска" stay compassionate.
- Tests: `api/tests/test_violence_keyword_fallback_languages.py` (block cases per language,
  narrative-benign cases under all 11 UI language codes, self-harm interplay, structural table
  checks, strict-xfail for en narrative gap from BITB-194). Stale comment in
  `test_safety_second_opinion.py` fixed.

## Verifier fixes (2026-10-17)

- Hard table: zh 炸彈/引爆/恐襲 and ru `взорв` stem added; a derived reconciliation test asserts every
  explosives/terror pattern of the violence table for ru/zh/hi/ko is also hard-matched, so the
  classifier cannot override them next to self-harm.
- ru: `застрел...` violence pattern guarded with `(?!\s+себя)`; `застрелиться`, `застрелю себя`,
  `застрелить себя` added to the ru self-harm table. Hard ru "attack" reduced to `напасть на` /
  `нападу на` (+ `нападен`), so "на меня напала тоска" stays compassionate.
- hi: `मारना चाहता/चाहती हूँ` requires an explicit other-person target (self-targets never match);
  `किसी को मार...` has a trailing Devanagari boundary and a `नहीं` guard.
- ko: past-tense `싶었` excluded from the `죽이고 싶` pattern.

## Known limitation (accepted, degraded mode)

Quoted first-person scripture such as ru "Почему Давид сказал Голиафу: я убью тебя?" and zh
"大卫对歌利亚说我要杀你，是什么意思？" stays blocked in fallback mode. The fallback has no quote
awareness; blocking is the safe direction while ML moderation is down. Documented, not xfail-tested.

Self-targeted shooting (hi `खुद को गोली मार…`, zh `对自己开枪`, `开枪自杀`) is covered by self-harm
patterns whose span contains the gun verb, so it is compassionate rather than a violence block.

## Follow-ups

- BITB-193 covers the missing `DIRECTED_HARM_PATTERNS` tables for ar/ru/zh/hi/ko (only
  en/it/de/es/fr/pt exist today).
- Recall gaps, to be filed as a story: word-order variants (ru "Я хочу его убить", "Я тебя убью";
  ko "총을 어디서 사나요"; zh "哪里买枪"), and UI-language scoping in step (e) of the fallback
  (non-self-harm violence is scoped to `[language, "en"]`).
- Native-speaker review of the new patterns (owner task).
- Recall gaps found by the verifier (non-regressions, to be filed together with the word-order story):
  ru `подорву`/`подорвать`, `Хочу убить своего начальника`, `пулю в лоб`; zh `我要炸学校`,
  `我要毒死他`, `我想杀死我老板`, `我想杀了我自己`; hi `अपने बॉस को मार डालूँगा`, `मुझे जीना नहीं है`;
  ko `나 자신을 죽이고 싶어`.
