---
id: BITB-335
status: todo
priority: P3
size: M
created: 2026-11-16
---

# BITB-335: Choose One Portuguese Variant Across Web and Android

**Follow-up of:** BITB-331 / BITB-334 (verifier findings, 2026-11-16).

## Problem

Web `frontend/messages/pt.json` is mostly European Portuguese ("Partilhe", "estou a") with a few Brazilian forms; Android `values-pt` is Brazilian ("Compartilhe"). The owner must pick one variant (or split pt-PT / pt-BR) before the strings are harmonised.

## Acceptance criteria

- [ ] Owner step: decide pt-PT, pt-BR or a split.
- [ ] Both platforms use the chosen variant consistently; key parity holds.
