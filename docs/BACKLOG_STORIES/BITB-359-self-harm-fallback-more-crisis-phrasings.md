---
id: BITB-359
status: todo
priority: P2
kind: fix
milestone: R1
size: S
created: 2026-11-24
---

# BITB-359: Self-Harm Fallback — More Crisis Phrasings Still Clean

## Problem

Follow-up to BITB-203/204. Probed with `ContentSafetyService._full_keyword_fallback` after those fixes
(2026-11-24), these first-person crisis phrasings still return `clean (fallback)`, so with ML moderation
down the person gets no compassionate path:

- en: "I don't want to live anymore", "I'd rather be dead"
- it: "Non voglio più vivere", "Ho pensieri suicidi"
- de: "Ich bringe mich heute um" (adverb between), "Ich töte mich", "Suizidgedanken"
- es: "No quiero vivir más"
- fr: "J'ai envie d'en finir", "Je ne veux plus vivre"
- pt: "Não quero mais viver"
- ar: "أريد أن انتحر" (hamza-less after أريد أن)

## Acceptance criteria

- [ ] Add specific first-person patterns for each phrasing (no bare "die"/"vivre" matches)
- [ ] Benign Bible-study questions stay clean (parametrized across all 11 languages)
