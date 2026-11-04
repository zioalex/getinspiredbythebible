# BITB-264: Directed-Harm Patterns Miss "Killing Yourself" Taunts and "You Should" Wishes

**Status:** 🎯 Todo
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

- [ ] "killing yourself" / "kill urself" / "kys" taunts block as directed harm; help-seeking frames from BITB-238 stay allowed
- [ ] Second-person "you should (do it|go)" wishes block
- [ ] Parametrized across the 11 language codes; no regression in BITB-193/BITB-238 tests
