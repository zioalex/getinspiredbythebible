# BITB-194: Fallback Violence Regex Blocks Bible-Narrative Questions

**Status:** 🔍 In Review
**Size:** S
**Created:** 2026-10-13

**As a** Bible-study user, **I want** questions about biblical battles and deaths answered even when ML moderation is down, **so that** an outage does not make the app refuse core content.

## Problem

Found while implementing BITB-185. The fallback violence patterns (en `\bkill\b`, `\battack\b`,
`\bweapon\b`, `\bgun\b`; es/pt `\bmatar\b`; fr `\btuer\b`; ...) are bare words, so "How did David
kill Goliath?" is blocked with `keyword_violation:violence (fallback)` when ML moderation is unavailable.

## Acceptance criteria

- [x] Bible-narrative questions (David/Goliath, Cain/Abel, Judas...) are allowed in the fallback, all 11 languages
- [x] Genuine intent phrasings ("I want to build a bomb", "how do I kill someone") still block
- [x] Parametrized cross-language tests (29 narrative cases x 11 UI languages; intent cases per language and for English under every UI code), evasion (zero-width, leet), `SOFT_VIOLENCE_TERMS` subset-of-table invariant
- [x] Step (b) (self-harm ambiguity) still sees method words (`gun`, `kill`, ...)

## Design

Only step (e) of `ContentSafetyService._full_keyword_fallback` changed. It now calls the new
`MultiLanguageContentFilter.find_fallback_violence_matches`, which uses
`_fallback_violence_regex[lang]`:

- en/it/de/es/fr/pt/ar: `VIOLENCE_PATTERNS[lang]` minus `SOFT_VIOLENCE_TERMS[lang]` (the bare
  weapon/gun/kill/murder/attack/shoot/stab/slaughter/terror words and their translations), plus a
  standalone `\bterroris` (terrorism/terrorist/terrorismo/terroriste/Terrorismus; not ar), plus
  `INTENT_VIOLENCE_PATTERNS[lang]`.
- ru/zh/hi/ko: unchanged table (already intent-gated by BITB-198).
- `INTENT_VIOLENCE_PATTERNS`: first-person intent ("I want / need / plan / am going to kill ...",
  allowing only -ly adverb filler), "let's / help me kill", how-to ("how do I / how to / best way to
  kill"), and acquisition ("where can I buy a gun"; "weapon of ..." excluded), with per-language
  equivalents. Verb patterns are gated by `_SPIRITUAL_OBJECT_EXCLUDE` (sin, pride, flesh, old self,
  ego, temptation, lust, time, giants and translations), so "How do I kill my sin and pride?" passes.
- Still standalone-blocking: bomb, explosive, grenade, molotov, napalm, ricin, anthrax, sarin,
  detonat, mass/school shooting, attentat/atentado, tiroteo, Sprengstoff, قنبلة, متفجر, تفجير,
  ناسف, إرهاب, ...
- Untouched: step (b), `VIOLENCE_PATTERNS`, `HARD_VIOLENCE_PATTERNS`, `DIRECTED_HARM_PATTERNS`,
  `HATE_SPEECH_PATTERNS`, the step-(e) language scope (`[language, "en", ru, zh, hi, ko]`).

## Accepted residual risks (fallback only, i.e. while ML moderation is down)

- Third-person threats ("he will kill her", "they are going to attack the school") and bare-noun
  requests ("send me a picture of a gun") now pass the keyword fallback. Hard terms, directed-harm
  (Stage 1) and the self-harm paths are unaffected.
- "You"-subject ethics questions ("How do you kill a man in self-defence?") and quotes such as
  "let's kill him" still block (the how-to / let's patterns do not know who speaks).
- Arabic intent patterns apply only when the UI language is `ar` (ar is not in the any-UI scope);
  see BITB-243.

## Follow-ups

- BITB-242: Stage-1 `HATE_SPEECH_PATTERNS` block scripture even with ML up
- BITB-243: widen fallback step (e) to every language incl. ar
