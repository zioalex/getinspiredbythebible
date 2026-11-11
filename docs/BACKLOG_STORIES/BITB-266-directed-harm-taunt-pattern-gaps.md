# BITB-266: Directed-Harm Patterns Miss "Killing Yourself" Taunts and "You Should" Wishes

**Status:** 🔍 In Review
**Priority:** P2
**Size:** S
**Created:** 2026-11-04

## Problem

Follow-up to BITB-238 (verifier findings, pre-existing on `main`). The English directed-harm table only
matches `kill yourself`, `go die` and `you should die`, so these pass Stage 1 and the keyword fallback
treats them as clean or help-seeking:

- "I hope you're thinking about killing yourself", "Start thinking about killing yourself"
- "Is it a sin? You should, loser." (no `die`, so nothing matches)

## Acceptance criteria

- [x] "killing yourself" / "kill urself" / "kys" taunts block as directed harm; help-seeking frames from BITB-238 stay allowed
- [x] Second-person "you should (do it|go)" wishes block
- [x] Parametrized across the 11 language codes; no regression in BITB-193/BITB-238 tests

## Resolution

Added named constants (`_DH_SLANG_KILL`, `_DH_KYS`, `_DH_WISH_TAUNT`, `_DH_IMPERATIVE_TAUNT`, `_DH_SHOULD_INSULT`, `_DH_SHOULD_DEATH_CTX`) to `DIRECTED_HARM_PATTERNS["en"]` in `api/utils/security.py`: slang `kill(ing) urself`/`kys`; negation-guarded `I hope/wish you ... killing yourself`; clause-start imperative `(just) start/keep/try ... thinking about killing yourself`; `you should (just) (do it|go ahead)` followed by an insult; and a bare `You should.` / `You should just do it!` only after a kill/suicide/die reference. Context-free "you should do it", negated wishes, conditionals and the BITB-238 help-seeking frames stay clean.

Tests: BITB-266 section in `api/tests/test_stage1_directed_harm_any_language.py` (blocked and clean corpora x 11 language codes, through `find_directed_harm_violation`, `check_multilingual`, the keyword fallback and `_check_stage1_keywords`). The fallback consults the same table, so it blocks these too.
