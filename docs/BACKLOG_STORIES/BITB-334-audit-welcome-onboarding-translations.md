---
id: BITB-334
status: todo
priority: P2
size: M
created: 2026-11-16
---

# BITB-334: Audit Welcome and Onboarding Translations in All 11 Languages

**Reported by:** a user via the owner, 2026-11-16: the Italian welcome subtitle said "Le Scritture
*parlano* conforto" instead of "*portano* conforto" (fixed in the first commit of this branch).
Spec confirmed by the owner in chat.

## Scope

Review for wrong verbs, grammar, register and meaning, in en, it, de, es, fr, pt, ar, ru, zh, hi, ko:

- **Android** (`android/app/src/main/res/values*/strings.xml`): `welcome_title`, `welcome_subtitle`,
  `about_intro_*`, `tour_*`.
- **Web** (`frontend/messages/*.json`): `Header.subtitle`, `Welcome.heading`, `Welcome.description`,
  `About.intro*`.

Out of scope: the 100 `Welcome.promptN` strings, other UI strings, the About page body.

## Requirements

1. Fix every clear error in place; keep meaning faithful to the English source.
2. List doubtful wording as a table in this story under *Needs native-speaker review*.
3. Add a regression test for the Italian typo (the string must contain "portano conforto" and not
   "parlano conforto") on Android resources.

## Acceptance criteria

- [ ] Every in-scope key reviewed in all 11 locales on both platforms; findings recorded below.
- [ ] Clear errors fixed; doubtful items listed.
- [ ] Italian regression test passes.
- [ ] `translation-validation` parity still holds (all keys in all locales).
