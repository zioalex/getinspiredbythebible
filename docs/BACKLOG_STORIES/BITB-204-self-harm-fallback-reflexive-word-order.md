# BITB-204: Self-Harm Fallback Misses "Kill Myself" Word-Order Variants (ru/zh/ko)

**Status:** 🎯 Todo
**Size:** S
**Created:** 2026-10-19

## Problem

Follow-up to BITB-198. «Хочу себя убить», 我想杀了我自己 and 나를 죽이고 싶어 are not matched by the
self-harm tables. BITB-198's violence patterns deliberately skip them, so with ML moderation down they stay
clean and the person gets no compassionate path.

## Acceptance criteria

- [ ] The three phrasings (and close variants) take the compassionate path in the fallback
- [ ] BITB-186 / BITB-198 benign Bible-study cases stay clean
- [ ] Parametrized across all 11 UI languages
