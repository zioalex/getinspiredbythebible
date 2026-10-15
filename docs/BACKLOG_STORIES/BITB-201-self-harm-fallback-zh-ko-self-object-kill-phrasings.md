# BITB-201: Self-Harm Fallback Misses Transitive "Kill Myself" Phrasings (ru/zh/hi/ko)

**Status:** 🎯 Todo
**Size:** S
**Created:** 2026-10-15

**As a** user in crisis writing in Russian, Chinese, Hindi or Korean, **I want** "kill myself"
phrasings with a self object to be recognised, **so that** I get the compassionate response when ML
moderation is down.

## Problem

Follow-up to BITB-198. The new violence patterns carry self-object guards so they never swallow a
self-harm phrase (they return neither a violence block nor, for the forms below, a compassionate
result). The self-harm fallback does not match these phrasings, so they come back **clean** (not
blocked, no compassionate response) today:

- zh: `我想杀了自己`, `我要杀死自己`, `我要杀掉自己`, `我想杀死我自己`, `我要杀了我自己`
- ko: `나를 죽이고 싶어요`, `저를 죽이고 싶어요`, `자신을 죽이고 싶어요`, `스스로 죽이고 싶어`,
  `자신을 죽일 거야`, `저 자신을 죽일 거예요`, `날 죽일 거야`, `나 자신 죽이고 싶어`
- hi: `अपने आप को मार डालना चाहती हूँ`, `खुद को गोली मार लूँगा`, `खुद को भी मार दूँगा`,
  `अपने को मार डालूँगा`
- ru: `Хочу себя убить`, `Хочу застрелиться`, `Хочу отравиться`, `Хочу убить самого себя`,
  `Я хочу убить и себя`

## Acceptance criteria

- [ ] The phrasings above trigger `compassionate_response_needed=True` (parametrized test)
- [ ] Third-person and Bible-narrative variants (`扫罗杀了自己`, `사울이 자신을 죽였다`) stay clean
- [ ] Parametrized across the 11 languages where an equivalent exists (assert, do not assume)
- [ ] BITB-198 violence and Bible-narrative tests still pass
- [ ] Reviewed by a native speaker (owner step)

## Out of scope

- Other self-harm recall gaps (BITB-200).
