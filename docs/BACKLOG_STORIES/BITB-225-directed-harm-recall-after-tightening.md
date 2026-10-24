# BITB-225: Directed-Harm Recall Lost by the BITB-193 Pattern Tightening (it/fr/pt)

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-24

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

- [ ] The phrasings above block, without reintroducing the BITB-193 false positives
- [ ] "die to sin/self" wording ("Spero che tu muoia in Cristo", "Que você morra para o pecado") stays unblocked
- [ ] Parametrized across the 11 language codes
