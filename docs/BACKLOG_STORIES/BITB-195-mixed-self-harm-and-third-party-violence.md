# BITB-195: Decision — Mixed Self-Harm and Third-Party Violence Messages

**Status:** Todo
**Size:** S
**Created:** 2026-10-13

**As a** product owner, **I want** a defined behaviour for messages combining self-harm and harm to others, **so that** safety handling is deliberate rather than an accident of check order.

## Problem

Found while implementing BITB-185. The fallback now checks self-harm before plain violence, so
"I will kill him and then myself" (no directed-harm phrase such as "I will kill you") is treated as
help-seeking and allowed with the compassionate flag. Clearly directed phrases still block first.

Mixed-case examples to cover:

- en "I will kill him and then kill myself"
- pt "Vou matar meu vizinho e depois me matar"
- Victim misclassification (the reverse problem): pt "Eles querem me matar" ("they want to kill
  me") matches the self-harm pattern `me matar` although the speaker is the victim.

## Acceptance criteria

- [ ] Decision recorded: block, compassionate, or compassionate plus review flag
- [ ] Behaviour implemented and tested across all 11 languages (parametrized)
