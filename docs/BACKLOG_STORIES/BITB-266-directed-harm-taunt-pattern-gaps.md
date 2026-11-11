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

Added named constants to `DIRECTED_HARM_PATTERNS["en"]` in `api/utils/security.py` (all deliberately narrow):

- `_DH_SLANG_KILL` / `_DH_KYS`: imperative `kill urself` / `kill yo self` and whole-word `kys`. "killing urself" alone is
  the overwork idiom and stays allowed.
- `_DH_WISH_TAUNT`: `hope/wish (that) you('re|were) (thinking about|considering|going to …)? kill(ing) yourself`, with no
  free gap, so grief letters ("I wish you had told me you were thinking about killing yourself") and caring wishes
  ("I hope you choose life instead of killing yourself") stay allowed.
- `_DH_IMPERATIVE_TAUNT`: clause-start `(just) start/keep/try/consider (thinking about) killing yourself`; a later
  `?` in the clause (hotline wording "Keep thinking about killing yourself? Call 988.") exempts it.
- `_DH_SHOULD_INSULT`: `you/u should (just) (do it|go ahead|go)` + insult (verbs like trash/freak/clown excluded);
  written as `(?:\s*,\s*|\s+)` to stay linear on whitespace runs.
- `_DH_SHOULD_DEATH_CTX`: a bare `You should.` / `You should just do it!` only after a second-person self-harm
  reference (kill yourself / suicide / end your life / better off dead). Dying relatives, "die to self" and Bible
  narrative ("Judas killed himself. You should.") stay allowed.

Independent verification found false positives in a first, broader draft (grief letters, dying relatives, overwork idiom,
hotline wording) and a quadratic-backtracking pattern; all were fixed and are pinned in the clean corpus, plus a
10k-character timing test.

Tests: BITB-266 section in `api/tests/test_stage1_directed_harm_any_language.py` (blocked and clean corpora × 11
language codes, through `find_directed_harm_violation`, `check_multilingual`, the keyword fallback and
`_check_stage1_keywords`). The fallback consults the same table, so it blocks these too.

## Follow-ups

- BITB-293 — remaining directed-harm gaps: reported speech (`My sister said 'kys' to me`), spaced/obfuscated `k y s`,
  `kil urself`, and context-free wishes ("Nobody would miss you. You should do it.", "I hope you die").
