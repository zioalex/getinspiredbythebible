# BITB-207: "Putting Sin to Death" Bible Questions Blocked by Native Violence Patterns (hi/ko/zh/ru)

**Status:** 🎯 Todo
**Size:** S
**Created:** 2026-10-18

Deferred from BITB-198 verification. Sanctification questions use killing verbs with a non-person object and still match the intent / how-to forms: hi `हम पाप को कैसे मारें?`, `शरीर के कामों को कैसे मारें?`, `मैं अपने पाप को मारना चाहता हूँ`; ko `죄를 죽이는 방법은?`, `옛 사람을 죽이는 법`, `내 안의 죄를 죽이고 싶어요`; zh `我想杀死心里的骄傲`, `我们要杀死老我`; ru `хочу убить свою похоть` (partly guarded with `в себе`/`свою` in BITB-198). Blocked with `keyword_violation:violence (fallback)` when ML moderation is down.

## Acceptance criteria

- [ ] Abstract-object guard (sin, flesh, old self, pride) in hi/ko/zh/ru
- [ ] Questions above are clean; real threats against people still blocked
- [ ] Parametrized tests
