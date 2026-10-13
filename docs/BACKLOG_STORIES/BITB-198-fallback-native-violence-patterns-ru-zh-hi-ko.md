# BITB-198: Keyword Fallback Has No Native Violence Patterns for ru/zh/hi/ko

**Status:** 🎯 Todo
**Size:** M
**Created:** 2026-10-13

## Problem

Follow-up to BITB-185 v2 (pre-existing at main): `VIOLENCE_PATTERNS` has no ru, zh, hi or ko entries, so plain violence (no self-harm) in those languages is clean in the fallback when ML moderation is down. BITB-185 v2 added a separate `HARD_VIOLENCE_PATTERNS` table (bombs, terror, massacre) used only next to self-harm; the general violence table was deliberately not edited.

## Acceptance criteria

- [ ] Native violence patterns for ru, zh, hi, ko with Bible-narrative false-positive review (see BITB-194)
- [ ] Parametrized tests across all 11 languages incl. CJK/fullwidth and Devanagari
- [ ] Hard-violence table reconciled with the violence table

## Note (from BITB-185 v2 verification)

ru verb `напасть` (to attack) is not covered by the ru hard-violence table (`нападен` only).
