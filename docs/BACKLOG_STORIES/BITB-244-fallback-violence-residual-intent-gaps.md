# BITB-244: Close Residual Fallback-Violence Intent Gaps

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-26

## Problem

Follow-up to BITB-194. The intent-gated keyword fallback (`INTENT_VIOLENCE_PATTERNS`) still lets
a few harmful phrasings through while ML moderation is down:

- Verbs with an attached pronoun: es `matarlo`, it `ucciderlo`, pt `matá-lo`, fr `tuez-le`.
- German separable verbs: "Ich werde ihn umbringen" style splits ("Ich bringe ihn um").
- Model-name weapons: "where to buy an AR-15" (the gun noun list has no model names).
- "strangle", "beat to death", "want him dead" (these already passed on main before BITB-194).

## Acceptance criteria

- [ ] Each phrasing above blocks in the fallback, with a parametrized cross-language test
- [ ] Bible-narrative and spiritual-metaphor cases (NARRATIVE_LATIN_AR) still pass under all 11 UI languages
