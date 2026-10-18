# BITB-198: Keyword Fallback Has No Native Violence Patterns for ru/zh/hi/ko

**Status:** 🔍 In Review
**Size:** M
**Created:** 2026-10-13
**Updated:** 2026-10-18

## Problem

Follow-up to BITB-185 v2 (pre-existing at main): `VIOLENCE_PATTERNS` has no ru, zh, hi or ko entries, so plain violence (no self-harm) in those languages is clean in the fallback when ML moderation is down. BITB-185 v2 added a separate `HARD_VIOLENCE_PATTERNS` table (bombs, terror, massacre) used only next to self-harm; the general violence table was deliberately not edited.

## Spec / Plan

Additive change to `api/utils/security.py` only (`content_safety.py` untouched): new `ru`, `zh`, `hi`, `ko` keys at the end of `VIOLENCE_PATTERNS`, plus two ru verb forms in `HARD_VIOLENCE_PATTERNS["ru"]` (`напасть на`, `нападу/нападём/нападем`) which closes the BITB-185 v2 note.

## Decisions

- **Intent-scoped design.** The general violence table is matched for the user's language + `en` and blocks outright, so it must not fire on Bible narrative (BITB-194). The new patterns therefore cover only (a) weapon / explosive / terror nouns and (b) first-person intent, future, or how-to forms of killing (`хочу убить`, `我要杀`, `मार डालूँगा`, `죽이고 싶`, `如何杀人`, ...). No bare killing verb or noun (убить, 杀, मार, 죽이) is in the table, so "How did David kill Goliath?", `Не убий`, `不可杀人`, `살인하지 말라` stay clean.
- **Hard-only terms.** These stay in `HARD_VIOLENCE_PATTERNS` only (they decide the ambiguous self-harm + violence case) because they collide with Bible narrative: ru `нападен`/`взрыв`/`расстрел`; zh `袭击`/`屠杀`/`爆炸`/`爆破`/bare `恐怖`; hi `हमला`/`नरसंहार`/bare `आतंक`/bare `विस्फोट`; ko `학살`/bare `폭발`.
- **Self-harm objects excluded.** Intent forms carry negative lookarounds (`себя`, `自己`, `खुद को`/`अपने को`/`आत्म`, `자신을`/`스스로`) so crisis messages (`Я хочу убить себя`, `ख़ुद को मार दूँगा`) stay compassionate rather than ambiguous. Devanagari boundaries are written inline, nukta is matched as `\u093c` because `normalize_text` NFKC-decomposes `क़`/`ख़`.
- **Accepted limitation.** A quoted first-person threat in narrative ("Исав сказал: убью Иакова", also "Как убить Голиафа") matches the intent forms and is blocked. Filed as BITB-205.
- **Verifier fixes (second commit).** hi `कैसे करें/मारें` patterns got the Devanagari boundary and `आत्म`/`आत्म-` guards (previously `आत्महत्या कैसे करें` was ambiguous); self-object lookbehinds were widened for hi (`खुदको`, `अपने आपको`, `स्वयं को`, `खुद की`, `अपनी`, `खुद को ही`, `खुद को गोली`), ko (`나를`, `날`, `저를`, `자기를`, `자신을`, `스스로`) on every killing pattern, ru (`себя убью`, `сам себя убью`) and zh (`杀死我`); zh `枪杀`/`槍殺` dropped (枪 = spear in the CUV), `杀价/杀毒` excluded; ru `надо` lookbehind dropped; ko `싶었` excluded; ru `в себе`/`свою` abstract-object guards. Hindi `आत्म हत्या` (spaced) added to the self-harm fallback.
- **Deferred.** "Putting sin to death" questions (BITB-207), hi third-person present intent (BITB-208), weapon noun next to a suicide phrase going ambiguous in ru/zh/ko/hi, same as en today (BITB-209).
- Weapon nouns block debate questions (`총기 규제`, `枪支`, `बंदूक नियंत्रण`); accepted for now, filed as BITB-206.

## Acceptance criteria

- [x] Native violence patterns for ru, zh, hi, ko with Bible-narrative false-positive review (see BITB-194)
- [x] Parametrized tests across all 11 languages incl. CJK/fullwidth and Devanagari
- [x] Hard-violence table reconciled with the violence table

Tests: `api/tests/test_violence_keyword_fallback_languages.py` (positives in all 11 languages, fullwidth/CJK brackets/zero-width/nukta/RTL variants, ~10 narrative cases each for ru/zh/hi/ko under own language and `en`, hard-only terms clean, pure crisis compassionate under all UI languages, mixed crisis + violence ambiguous, table-invariant tests; BITB-194 en/ar cases are `xfail(strict)`).

## Follow-ups

- BITB-204: self-harm fallback misses zh `杀了自己`/`杀死自己`, ko `자신을 죽이고 싶` and hi `अपने को मार दूँगा` (hi spaced `आत्म हत्या` was fixed in the verifier-fix commit)
- BITB-205: quoted first-person threat in narrative ("Исав сказал: убью Иакова") is blocked
- BITB-206: weapon-noun debate questions (`총기 규제`, `枪支管制`, `बंदूक नियंत्रण`) are blocked
- BITB-207: "putting sin to death" Bible questions blocked (hi/ko/zh/ru)
- BITB-208: hi present-tense third-person intent blocked
- BITB-209: weapon noun next to a suicide phrase goes ambiguous in ru/zh/ko/hi
