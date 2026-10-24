# BITB-235: Stage 1 Blocks English "Kill Yourself" Help-Seeking and Theological Questions in Every UI Language

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-24

## Problem

Follow-up to BITB-193 (verifier finding). Stage 1 now runs every language's directed-harm table
regardless of the detected-language code, so the English patterns (`kill yourself`, `go die`,
`you should die`) apply under all 11 codes. They already blocked these under `en`; the fallback has
behaved this way since BITB-185. Examples now blocked as `directed_harm` instead of reaching the model
or the compassionate path:

- "Is it a sin to kill yourself?" (help-seeking)
- "What happens if you kill yourself?"
- "Why did Jesus have to go die on the cross?"
- "Does Paul say you should die to sin daily?"

## Acceptance criteria

- [ ] Question-form and theological uses of the English phrases are not blocked as directed harm
- [ ] Genuine second-person threats ("Go kill yourself", "You should die") still block under all 11 codes
- [ ] Help-seeking forms route to the compassionate path
- [ ] Parametrized across the 11 language codes; no regression in BITB-193 tests
