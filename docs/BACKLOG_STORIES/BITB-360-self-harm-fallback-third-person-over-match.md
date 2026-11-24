---
id: BITB-360
status: todo
priority: P2
size: S
created: 2026-11-24
---

# BITB-360: Self-Harm Fallback — Third-Person and Idiom Over-Matches Get the Crisis Card

## Problem

Follow-up to BITB-203/204. Residual over-matches (fail toward the compassionate path, consistent with
pre-existing patterns such as `убить себя`), probed 2026-11-24:

- ru `себя убить` / `убить себя` ignore the subject: "Почему Саул решил себя убить?" and
  "Он хотел себя убить" take the compassionate path.
- hi "खुद को और दूसरों को मारने वाले के बारे में बाइबल क्या कहती है" matches the new
  `खुद को और … मारने` span (clean on main).
- `_has_crisis_wording` (security.py) is now also true for de "Ich nehme meine Familie mit in die
  Kirche" (new de murder-suicide `nehme … mit`) and zh "请为自己和家人祈祷" (new `自己和家人`). Only effect: the
  profanity / repeated-char route filter steps aside for those messages.
- Any further over-match found in review.

## Acceptance criteria

- [ ] Add third-person guards where a reliable guard exists, without regressing first-person phrasings
- [ ] Narrow the de/zh murder-suicide patterns so `_has_crisis_wording` stays false for the benign examples
- [ ] Parametrized across all 11 languages
