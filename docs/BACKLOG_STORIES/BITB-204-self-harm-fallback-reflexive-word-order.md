---
id: BITB-204
status: in-review
priority: P2
size: S
created: 2026-10-19
prs: [1336]
---

# BITB-204: Self-Harm Fallback Misses "Kill Myself" Word-Order Variants (ru/zh/ko)

## Problem

Follow-up to BITB-198. «Хочу себя убить», 我想杀了我自己 and 나를 죽이고 싶어 are not matched by the
self-harm tables. BITB-198's violence patterns deliberately skip them, so with ML moderation down they stay
clean and the person gets no compassionate path.

## Acceptance criteria

- [ ] The three phrasings (and close variants) take the compassionate path in the fallback
- [ ] BITB-186 / BITB-198 benign Bible-study cases stay clean
- [ ] Parametrized across all 11 UI languages

## Spec (2026-11-24)

**Problem (verified on main 2026-11-24):** «Хочу себя убить», 我想杀了我自己, 나를 죽이고 싶어 returned
`clean (fallback)`.

**Functional requirements:** add ru `себя убить`, zh first-person `(我|想|要…)杀(了|死)(我)自己` (never after
他/她, never `自己的`), ko final form: `(나를|날|나 자신을|내 자신을) ?죽이고 ?싶` only; the 죽이겠/죽이려 forms are dropped (they are threats against the speaker), no other subject (noun + 이/가/은/는/께서) may precede 나를/날 unless it is 내가/나는, and `싶어해/싶어한다` (third person) is excluded. Benign BITB-186/198 cases
unchanged, asserted in `api/tests/test_self_harm_fallback_phrasings.py`.

**Acceptance criteria**

- [x] The three phrasings (and close variants) take the compassionate path in the fallback
- [x] BITB-186 / BITB-198 benign Bible-study cases stay clean
- [x] Parametrized across all 11 UI languages
