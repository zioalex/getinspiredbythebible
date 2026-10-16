# BITB-201: Murder-Suicide Fallback — Trailing Words and Missed Targets

**Status:** Todo
**Size:** S
**Created:** 2026-10-16

Follow-up to BITB-196 (Opus verifier finding). The clause-end guard misses common forms: "kill myself and my family now/tonight", "...and my family because they hate me", "kill myself and the kids", "...and everyone at school"; equivalents likely in the other 10 languages. Also "my wife and kids too" (no leading "and") and ru "убью себя и заберу всех с собой", it "uccidermi insieme alla mia famiglia".

## Acceptance criteria

- [ ] Time words and extra targets matched in all 11 languages (parametrized)
- [ ] Plain self-harm and prayer phrasings stay compassionate-only
