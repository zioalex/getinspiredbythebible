---
id: BITB-239
status: done
priority: P2
size: S
created: 2026-10-24
prs: [1261]
---

# BITB-239: Directed-Harm Recall Lost by the BITB-193 Pattern Tightening (it/fr/pt)

**Migration note (2026-11-13, status):** PR #1261, 2026-11-10

## Problem

Follow-up to BITB-193 (verifier finding). Tightening the single-word `muori`, `crève`, `morra`
patterns removed false positives but also some real threats that blocked before, now clean in Stage 1
and the keyword fallback (Stage 2 ML still catches them when up):

- it "ok muori", "adesso muori!", "Muori adesso!", "Sei inutile, muori."
- fr "Crève charogne"
- pt "morra seu idiota"

Causes: only a comma or end of text may follow the word; the insult list lacks a word in between
("seu idiota") and "charogne"; a comma before the word is not a clause start.
Also: "Spero che tu muoia in Cristo e risorga" is newly blocked, and "J'espère que tu vas crever" is missed.

## Acceptance criteria

- [x] The phrasings above block, without reintroducing the BITB-193 false positives
- [x] "die to sin/self" wording ("Spero che tu muoia in Cristo", "Que você morra para o pecado") stays unblocked
- [x] Parametrized across the 11 language codes

## Resolution

All changes in `api/utils/security.py` (directed-harm tables, constants beside `_DH_START`/`_DH_END`):

- it: optional lead-in (`ok`, `adesso`, `ora`, `dai`, `forza`) and tail (`adesso`, `ora`, `subito`, `presto`) around `muori`;
  new comma-led clause (`, muori.`) that needs a strong terminator (`!`, `.` or end) so "Ok, muori?" stays clean;
  `spero che tu muoia` now exempts the die-to-sin/Christ tail (`in Cristo`, `al peccato`, ...) and a `muoia ... <insult>` pattern was added.
- fr: `crève` accepts `sale`/`espèce de` and `charogne`, `enfoiré`, `pourriture`; new `que tu vas crever` (not `de rire`/`d'ennui`).
- pt: `morra` accepts `seu/sua` before the insult, plus `imbecil`, `otári`; `que você/tu morra` exempts `para o pecado`, `em Cristo`, ...
  (note: "Que você morra para o pecado" was also blocked before BITB-193 tightening). No comma-led `morra` clause (it is the Italian game word).
- Tests: BITB-239 section in `api/tests/test_stage1_directed_harm_any_language.py` (recovered threats, die-to-sin, tightening negatives, x11 codes)
  and extra cases in `test_self_harm_keyword_fallback_languages.py`.

Known limit: pt "Que você morra para o pecado, seu idiota" is not blocked (the die-to-sin lookahead exempts the plain pattern and there is no pt `morra ... insult` tail pattern); it is caught for it via the `muoia ... <insult>` pattern.
