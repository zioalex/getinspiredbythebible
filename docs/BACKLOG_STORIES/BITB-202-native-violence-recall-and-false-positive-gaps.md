# BITB-202: Native Violence Patterns — Recall Gaps and Known False Positives (ru/zh/hi/ko/de)

**Status:** 🎯 Todo
**Size:** M
**Created:** 2026-10-15

Follow-up to BITB-198 (independent verification findings).

## Genuine threats still clean in the fallback

- zh: `我想把他杀了`, `我杀了你`, `我明天要去学校杀人`
- ru: `Хочу всех перестрелять`
- ko: `총을 어디서 사요?`

## False positives that block today

- Weapon noun next to self-harm goes to the ambiguous crisis block (`我想用手枪自杀`,
  `बंदूक से खुद को मार दूँगा`, `권총으로 죽고 싶어요`).
- Spiritual "kill sin/pride": ru `Как убить в себе гордыню?`, hi and ko `죄를 죽이고 싶어요`.
- ko third-person `-ㄹ 거예요` / `싶은` forms.
- zh slang `杀价` / `杀毒` / `杀时间`.
- de `Anschlag` in Luther's sense of "plot".

## Acceptance criteria

- [ ] The genuine threats above block (parametrized, with Bible-narrative cases still clean)
- [ ] Each false positive above is allowed, or an explicit decision is recorded
- [ ] Reviewed by a native speaker (owner step)
