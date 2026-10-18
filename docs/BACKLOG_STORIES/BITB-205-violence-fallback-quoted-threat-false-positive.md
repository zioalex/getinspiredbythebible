# BITB-205: Violence Fallback Blocks Quoted First-Person Threats in Bible Narrative

**Status:** 🎯 Todo
**Size:** S
**Created:** 2026-10-18

Known limitation accepted in BITB-198. The ru intent patterns match `убью`, `хочу убить`, `как убить`, so questions quoting a narrative threat ("Исав сказал: убью Иакова, брата моего", "Как убить Голиафа") are blocked with `keyword_violation:violence (fallback)` when ML moderation is down. The same shape exists for zh `我要杀`, hi `मार डालूँगा`, ko `죽이고 싶`. Related to BITB-194.

## Acceptance criteria

- [ ] Decide a rule (for example a quote or name-object guard) that keeps real threats blocked
- [ ] Narrative quote cases pass in ru/zh/hi/ko without weakening BITB-198 positives
- [ ] Parametrized cross-language tests
