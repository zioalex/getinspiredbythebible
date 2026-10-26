# BITB-242: Stage-1 Hate-Speech Patterns Block Scripture Even With ML Up

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-26

## Problem

Follow-up to BITB-194. `MultiLanguageContentFilter.HATE_SPEECH_PATTERNS["all"]` contains
`\bdeath to\b` and `\bkill all\b`. Stage 1 (`check_multilingual` / `find_directed_harm_violation`)
runs these regardless of ML moderation health, so ordinary Bible questions are blocked as
`hate_speech` even when everything is up. Verified on 2026-10-26 against the code:

- "He passed from death to life" -> `('hate_speech', 'all', 'death to')`
- "Did God tell Israel to kill all the Canaanites?" -> `('hate_speech', 'all', 'kill all')`

Other entries (`exterminate`, `god hates`) deserve the same review.

## Acceptance criteria

- [ ] Scripture/narrative phrasings above (and equivalents) are allowed in Stage 1
- [ ] Genuine hate speech ("death to all <group>", "kill all <group>") still blocks
- [ ] Parametrized cross-language regression tests (11 languages) plus the existing golden set stay green
