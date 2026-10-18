# BITB-204: Self-Harm Fallback Misses zh/ko/hi Reflexive Killing Forms

**Status:** 🎯 Todo
**Size:** S
**Created:** 2026-10-18

Found while reviewing BITB-198. The self-harm keyword fallback does not fire on these first-person phrasings (verified against `find_all_self_harm_spans`): zh `我想杀了自己` / `我要杀死自己`, ko `자신을 죽이고 싶어요`, hi `अपने को मार दूँगा` (spaced `आत्म हत्या` was fixed under BITB-198). BITB-198's intent patterns deliberately exclude these self-harm objects, so such messages currently come out as clean in the fallback instead of compassionate.

## Acceptance criteria

- [ ] Each phrasing above triggers the compassionate path in the fallback (parametrized test)
- [ ] Bible-narrative cases from BITB-198 stay clean
- [ ] No new match for ru `убить себя`-style forms regresses
