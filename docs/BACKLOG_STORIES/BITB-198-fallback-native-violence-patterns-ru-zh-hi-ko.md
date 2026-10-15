# BITB-198: Keyword Fallback Has No Native Violence Patterns for ru/zh/hi/ko

**Status:** 🔍 In Review
**Size:** M
**Created:** 2026-10-13

**As a** user writing in Russian, Chinese, Hindi or Korean, **I want** violent threats to be blocked
even when ML moderation is down, **so that** the outage does not turn the app into an unfiltered
channel, **without** blocking ordinary Bible-study questions about scripture's violent narrative.

## Problem

Follow-up to BITB-185 v2 (pre-existing at main): `VIOLENCE_PATTERNS` had no ru, zh, hi or ko
entries, so plain violence (no self-harm) in those languages was clean in the fallback when ML
moderation is down. BITB-185 v2 added a separate `HARD_VIOLENCE_PATTERNS` table (bombs, terror,
massacre) used only next to self-harm; the general violence table was deliberately not edited.
Note (from BITB-185 v2 verification): the ru verb `напасть` was not covered by the hard table.

## Functional requirements

- Native ru/zh/hi/ko entries in `VIOLENCE_PATTERNS` describing intent (first-person future or
  desire, "how to" questions), not bare verbs: Bible narrative is third person / past tense.
- Bare nouns only where they never occur in scripture (bomb, explosives, terror, grenade, molotov,
  pistol, rifle).
- Massacre words stay in `HARD_VIOLENCE_PATTERNS` only. Every other hard term is also in the
  general table, except terms needing the hard filter's context exclusions (reconciliation rule
  documented next to the tables).
- Kill/attack patterns never swallow a self-harm phrase (self-object guards).
- Step (e) of the fallback also scans `SCRIPT_DISJOINT_VIOLENCE_LANGS`
  (ar, ru, zh, hi, ko), so native-script threats block when the detector returns `en`.

## Non-functional requirements

- All 11 languages covered by parametrized tests, incl. CJK/fullwidth punctuation, Devanagari, RTL.
- No LLM call; patterns are regex only (each fallback check stays well under 5 ms).
- Deliberately excluded for scripture false positives: zh bare 枪 (spear), ru bare гранат
  (pomegranate), оружие/武器/무기/हथियार, zh 炸/爆炸 alone, ko 폭발, hi आतंकित.

## Acceptance criteria

- [x] Native violence patterns for ru, zh, hi, ko with Bible-narrative false-positive review (see BITB-194)
- [x] Parametrized tests across all 11 languages incl. CJK/fullwidth and Devanagari
- [x] Hard-violence table reconciled with the violence table
- [x] Self-harm phrasings still take the compassionate path (ru/hi/ko/zh tests)
- [x] ru `напасть` added to the hard table
- [ ] Native-speaker review of the new ru/zh/hi/ko patterns (owner step)

## Out of scope

- en/it/de/es/fr/pt/ar bare-verb false positives ("How did David kill Goliath?"): BITB-194
  (pinned as strict xfails in the new test file).
- Blocked-response templates: BITB-197.

## Accepted limitations

- First-person quoted scripture still blocks, e.g. Gen 27:41 "я убью Иакова".
- zh `该隐怎么杀人` ("how did Cain kill someone") matches the "how to kill a person" pattern.
- A weapon noun next to self-harm (`我想用手枪自杀`, `बंदूक से खुद को मार दूँगा`,
  `권총으로 죽고 싶어요`) goes to the ambiguous crisis block.
- Spiritual "kill sin/pride" phrasings block (ru `Как убить в себе гордыню?`, hi, ko `죄를 죽이고 싶어요`).
- ko third-person `-ㄹ 거예요` / `싶은` forms block.
- zh slang `杀价` / `杀毒` / `杀时间` blocks.
- de `Anschlag` (Luther's "plot") blocks.
- Hard-only terms (massacre family, bare attack nouns/verbs) are clean on their own and only
  matter next to self-harm.

## Implementation notes

- Patterns: `api/utils/security.py` (`VIOLENCE_PATTERNS`, `HARD_VIOLENCE_PATTERNS`,
  `SCRIPT_DISJOINT_VIOLENCE_LANGS`, `_HI_SELF`); `api/utils/content_safety.py` step (e).
- Tests: `api/tests/test_violence_keyword_fallback_languages.py`; ambiguity rows added to
  `api/tests/test_safety_second_opinion.py`.

## Follow-ups

- BITB-201: transitive self-harm phrasings (ru/zh/hi/ko) that the new self-object guards exclude.
- BITB-202: remaining recall gaps and the false positives listed above.
