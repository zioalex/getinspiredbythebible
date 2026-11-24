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

## Victim-of-threat (pre-existing on main)

On origin/main, victims of threats already get `possible_help_seeking (fallback)`: es "Mi padre quiere
matarme", fr "Mon mari veut me tuer", pt "Meu marido quer me matar", de "Mein Vater will mich
umbringen" (pre-existing `matarme` / `me tuer` / `me matar` / `mich umbringen`). The new BITB-203/204
patterns require a first-person lead so they do not widen this. **Owner decision needed:** should a
victim of threats get the compassionate/crisis card (current), a block, or a dedicated victim-safety
response?

## Residuals not closed in BITB-203/204

- en "Satan wants me to believe I'm better off dead", "Is suicidal ideation addressed in the Psalms?"
  and "My neighbor is suicidal" take the compassionate path (the `suicidal` exclusion list is
  deliberately not extended with thoughts/ideation, which are genuine crisis wording).
- ko God-as-question forms with an unusual subject/marker layout; the guard is subject-marker based.

## Third-person "X is/was suicidal" (new in #1336, fails toward compassionate)

`suicidal` / `suicidaire` / `suizidal` carry no subject guard, so on main (clean) these now take the
compassionate path: "Was Judas suicidal?", "Why was Saul suicidal?", "Elijah was suicidal under the
broom tree", "Élie était-il suicidaire ?", "War Elia suizidal?", and relatives "My mom is suicidal",
"Mon fils est suicidaire", "Mein Sohn ist suizidal", zh "丈夫想杀了自己和我" (the last is a 杀了自己 pattern
with a 丈夫 subject; it is clean after the round-3 guard, listed for completeness).
**OWNER DECISION:** accept the over-match to the compassionate card (consistent with bare "suicide" on
main) vs. require a first-person lead (risk: missing "suicidal" in short crisis messages such as
"so suicidal tonight"). Also accepted-or-owner-decision: it "Mio figlio vuole farla finita" (relative
case) is now clean.

## Acceptance criteria

- [ ] Add third-person guards where a reliable guard exists, without regressing first-person phrasings
- [ ] Narrow the de/zh murder-suicide patterns so `_has_crisis_wording` stays false for the benign examples
- [ ] Parametrized across all 11 languages
