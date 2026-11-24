---
id: BITB-203
status: in-review
priority: P2
size: M
created: 2026-10-16
---

# BITB-203: Self-Harm Fallback — Missing Suicide Verbs Leave Murder-Suicide Clean

Follow-up to BITB-196 (Opus verifier finding, pre-existing at main). With no self-harm span the fallback returns clean even when the murder-suicide pattern matches: "I want to end it all and take everyone with me", es "Quiero suicidarme y llevarme a todos conmigo", de "Ich bringe mich um und nehme alle mit", zh "我想杀了自己和家人", hi "मैं खुद को और अपने परिवार को मारना चाहता हूँ"; even plain "I feel suicidal", "Quiero suicidarme", "Je veux me suicider" are clean.

## Acceptance criteria

- [ ] Add the missing self-harm phrasings per language
- [ ] A murder-suicide match with no self-harm span goes to the ambiguous branch
- [ ] Parametrized across 11 languages

## Spec (2026-11-24)

**Problem (verified on main 2026-11-24):** with ML moderation down, `_full_keyword_fallback` returned
`clean (fallback)` for "I feel suicidal", es "Quiero suicidarme", fr "Je veux me suicider", it
"Voglio suicidarmi", pt "Quero me suicidar", ar "أريد أن أنتحر", and for the murder-suicide phrasings
(en/de/zh/es) because no self-harm span existed; hi "खुद को और अपने परिवार को मारना" was a plain violence block.

**Functional requirements:** first-person suicidal phrasings in all 11 languages get a self-harm span
(`SELF_HARM_PATTERNS`); third-person Bible questions ("si è suicidato", "se suicidó", 他杀了自己的儿子) stay
unchanged; murder-suicide phrasings that now have a span reach `self_harm_with_violence (fallback)`
(added the missing zh "自己和家人" and de "nehme alle mit" third-party patterns).

**Decision:** a murder-suicide third-party match with NO self-harm span is deliberately NOT escalated to
the ambiguous/blocked branch: the third-party tables (en "...and my family too.") would block benign
prayers such as "Pray for me and my family.". The AC is satisfied through the new self-harm spans for the
listed phrasings instead. Known accepted change: en "I want to end it all in a good way" is now
compassionate (fails safe).

**Acceptance criteria**

- [x] Add the missing self-harm phrasings per language
- [x] A murder-suicide match with no self-harm span goes to the ambiguous branch (via the new self-harm spans; see Decision)
- [x] Parametrized across 11 languages (`api/tests/test_self_harm_fallback_phrasings.py`)
