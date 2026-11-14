---
id: BITB-194
status: todo
priority: P2
size: S
created: 2026-10-13
---

# BITB-194: Fallback Violence Regex Blocks Bible-Narrative Questions

**As a** Bible-study user, **I want** questions about biblical battles and deaths answered even when ML moderation is down, **so that** an outage does not make the app refuse core content.

## Problem

Found while implementing BITB-185. The fallback violence patterns (en `\bkill\b`, `\battack\b`,
`\bweapon\b`, `\bgun\b`; es/pt `\bmatar\b`; fr `\btuer\b`; ...) are bare words, so "How did David
kill Goliath?" is blocked with `keyword_violation:violence (fallback)` when ML moderation is unavailable.

## Acceptance criteria

- [ ] Bible-narrative questions (David/Goliath, Cain/Abel, Judas...) are allowed in the fallback, all 11 languages
- [ ] Genuine intent phrasings ("I want to build a bomb", "how do I kill someone") still block
