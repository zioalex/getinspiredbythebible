---
id: BITB-334
status: in-review
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

## Audit findings (2026-11-16)

All in-scope keys were read in all 11 locales on both platforms against the English source.

### Fixed in place

| Locale | Key(s) | Was | Now / why |
| ------ | ------ | --- | --------- |
| it | Android `welcome_subtitle` | "parlano conforto" | "portano conforto" (first commit) |
| es | Android `welcome_subtitle` | "Las Escrituras hablan consuelo" | "traen consuelo" (same literal calque of "speaks comfort") |
| pt | Android `welcome_subtitle` | "A Escritura fala conforto" | "traz conforto" (same calque) |
| de | Android `welcome_subtitle` | "spricht Trost ... in jede Lebenslage" | "schenkt Trost ... in jeder Lebenslage" (wrong verb and case) |
| ar | Android `welcome_subtitle` | "يتكلم بالعزاء" | "يمنح العزاء" (verb of giving, not speaking) |
| hi | Android `tour_step_indicator` | "चरण %1$d का %2$d" | "चरण %1$d / %2$d" (ungrammatical "step 1 of 4") |
| hi | Web `Welcome.description` | "धार्मिक विषयों" (religious) | "धर्मशास्त्रीय विषयों" (theological) |
| fr, ru | `welcome_title`, `splash_motto`, web `Header.subtitle`, `Metadata.description`, motto | informal tu ("Laisse-toi", "Вдохновляйся") | formal vous ("Laissez-vous", "Вдохновляйтесь"), matching the rest of the UI |
| zh | Web `About.introBody` | ASCII commas "," | fullwidth "，" (matches the Android string) |
| pt | Web `Welcome.description`, chat input placeholder | European "Partilhe" mixed with Brazilian "celular/você" | Brazilian "Compartilhe" |

### Needs native-speaker review

| Locale | Key(s) | Concern |
| ------ | ------ | ------- |
| es | `about_intro_body` | "gentil" is a calque of "gentle"; "amable"/"cercano" may read better |
| ko | `about_intro_body` | Long relative clause before "동반자"; reads as a stack of modifiers |
| ko | web `Welcome.appBody` | "비공개로, 오직 당신만을 위해" is terse and slightly stilted |
| ko | `tour_step_indicator` | "%1$d/%2$d단계" vs "%2$d단계 중 %1$d단계" |
| zh | `About`/`Welcome` | "牧灵辅导" is Catholic-leaning; Protestant users may expect "牧养/牧会" |
| zh | web `Welcome.description` vs Android | 您 (formal) on web, 你 (informal) on Android |
| hi | `about_intro_body`, `Welcome.description` | "पास्टरल" is a transliteration; "पादरी-संबंधी" may be more natural. Self-reference uses masculine "सकता हूं" |
| ar | tour strings | MSA tone is fine; "الدردشة" vs "المحادثة" is inconsistent across the app |
| ru | `welcome_subtitle` | "тяготы" is slightly formal for a comfort message |
| it, de, es | `welcome_title` | Informal "tu/du" title but the surrounding copy mixes registers on some screens |
| es, pt | `Welcome.heading` | "Bienvenido"/"Bem-vindo" default to the masculine form |

### Regression test

`android/app/src/test/kotlin/org/voxquieta/app/i18n/WelcomeTranslationsTest.kt` reads the resource
XML and asserts Italian `welcome_subtitle` contains "portano conforto" and not "parlano conforto",
and that es/pt/de no longer use the "speaks comfort" calque.
