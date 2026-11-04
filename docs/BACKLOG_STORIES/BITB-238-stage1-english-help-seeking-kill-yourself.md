# BITB-238: Stage 1 Blocks English "Kill Yourself" Help-Seeking and Theological Questions in Every UI Language

**Status:** 🔍 In Review
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

## Known limitations

The exemptions are deliberately narrow and regex-based, so some benign phrasings still block:

- The exemption is a closed whole-message allowlist (single sentence, no hostile/encouraging word anywhere, must fully match one frame), so unusual phrasings of help-seeking go through the old block path. Acceptable: Stage 2 handles normal operation.

- "Why did Jesus go die for the world?" (only "on the cross" / "for our sins|my sins|sinners|mankind|humanity" are exempt, and only with a Jesus/Christ/he/God subject and no "you" earlier in the clause).
- "you should die for Christ" and similar martyrdom phrasing are not exempt; only "to sin/self/flesh..." and "daily/every day" suffixes are.
- Moral frames must be question-form ("Is it a sin to kill yourself?"); a statement such as "it is ok to kill yourself" blocks.
- Any "do it / go ahead / act on it" later in the message cancels every exemption, even in an unrelated clause.
- Whitespace runs between words are matched by the English patterns, but other evasions (leetspeak, misspellings) are out of scope.
