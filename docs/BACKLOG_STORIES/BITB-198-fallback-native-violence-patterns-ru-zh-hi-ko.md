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

## Spec

- **User story:** when ML moderation is down, plain violence in ru/zh/hi/ko is blocked like en/it/de/es/fr/pt/ar.
- **Functional:** conservative native patterns in `VIOLENCE_PATTERNS`; checked under any UI language
  (`_UNIQUE_SCRIPT_VIOLENCE_LANGS` in `content_safety.py`; `ar` excluded because of BITB-194);
  modern hard terms (grenade, Molotov, attentat, ...) added to the existing 7 languages; ru «напасть на»
  and missing zh/hi/ko terms added to the hard table.
- **Non-functional:** all 11 languages tested; CJK/fullwidth punctuation, Devanagari (nukta, anusvara,
  danda), zero-width evasion.
- **Out of scope:** BITB-194 (Latin/ar Bible-narrative false positives, pinned as strict xfail),
  BITB-193 (ru/zh/hi/ko directed harm), BITB-204 (self-harm word-order variants).

## Design

Unambiguous weapon/terror words match alone. Kill/attack verbs match only in first-person intent or
how-to phrasing, so «Как Давид убил Голиафа?» stays allowed. Words with Bible/everyday senses
(massacre, attack, bare explosion, ru оружие, hi हथियार) stay hard-only (checked next to self-harm).
Reflexive lookaheads/lookbehinds keep "kill myself" spans out of the violence table.

Accepted limitations: quoted first-person scripture speech (Esau's "I will kill ...") blocks while ML
is down; slang «бомба» blocks; the ru «не» guard is fixed-width.
