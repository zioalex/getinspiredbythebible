# BITB-203: Self-Harm Fallback — Missing Suicide Verbs Leave Murder-Suicide Clean

**Status:** Todo
**Size:** M
**Created:** 2026-10-16

Follow-up to BITB-196 (Opus verifier finding, pre-existing at main). With no self-harm span the fallback returns clean even when the murder-suicide pattern matches: "I want to end it all and take everyone with me", es "Quiero suicidarme y llevarme a todos conmigo", de "Ich bringe mich um und nehme alle mit", zh "我想杀了自己和家人", hi "मैं खुद को और अपने परिवार को मारना चाहता हूँ"; even plain "I feel suicidal", "Quiero suicidarme", "Je veux me suicider" are clean.

## Acceptance criteria

- [ ] Add the missing self-harm phrasings per language
- [ ] A murder-suicide match with no self-harm span goes to the ambiguous branch
- [ ] Parametrized across 11 languages
