# BITB-202: Murder-Suicide Fallback — Tie the Match to the Self-Harm Clause

**Status:** Todo
**Size:** S
**Created:** 2026-10-16

Follow-up to BITB-196 (Opus verifier finding). Matches are not tied to the self-harm clause, so "I want to die. Please pray for my wife and my kids.", it "...ne ho parlato con mia moglie" (`con` too broad), ko "가족과 함께 가고 싶어요" (`가` in verb list), ru "Я хочу умереть, я люблю жену и детей." go to the ambiguous branch (crisis block when the classifier is down). Safe direction, but noisy.

## Acceptance criteria

- [ ] Require proximity (same sentence or ~30 chars) to the self-harm span; drop broad `con/avec/com`, bare "everyone" and ko `가`
- [ ] Benign help-seeking cases listed above stay compassionate-only (all 11 languages)
