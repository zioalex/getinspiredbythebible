# BITB-295: Directed Harm — Reported Speech, Obfuscated "kys" and Context-Free Death Wishes

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-11-11
**Follow-up of:** BITB-266 (verifier findings on #1283)

## Problem

Checked against `DIRECTED_HARM_PATTERNS["en"]` in `api/utils/security.py` after BITB-266:

1. **Reported speech is blocked (false positive).** "My sister said 'kys' to me and I'm hurt. What does the Bible say
   about forgiving her?" and "My sister said 'kill yourself' to me" (the latter already on `main` before BITB-266) are
   blocked as directed harm, turning away a hurt user asking for help. "What does kys mean?" is blocked too.
2. **Obfuscation is missed (false negative).** "k y s", "k.y.s", "kil urself", "k!ll urself" match nothing.
3. **Context-free death wishes are missed (false negative).** "Nobody would miss you. You should do it.",
   "I hope you die", "nobody likes you, you should just die" pass Stage 1. Stage 2 ML catches them when it is up.
4. Leet normalisation turns "ky5" / "Ky$" into "kys" (low impact; no realistic word in the 11 languages found).

## Acceptance criteria

- [ ] Reported-speech frames ("X said/told me/called me '…'") followed by a help-seeking question are not blocked;
      the direct taunt still blocks
- [ ] Spaced/punctuated `kys` and `kil(l) urself` variants block
- [ ] "I hope you die" / "you should (just) do it" after a second-person worthlessness phrase block, without
      re-introducing the BITB-266 grief/pastoral false positives (that clean corpus stays green)
- [ ] Parametrized across the 11 language codes; a whitespace-run timing test for any new pattern
