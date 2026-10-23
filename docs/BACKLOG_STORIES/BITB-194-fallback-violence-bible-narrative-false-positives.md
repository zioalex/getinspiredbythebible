# BITB-194: Fallback Violence Regex Blocks Bible-Narrative Questions

**Status:** 🔍 In Review
**Size:** S
**Created:** 2026-10-13

**As a** Bible-study user, **I want** questions about biblical battles and deaths answered even when ML moderation is down, **so that** an outage does not make the app refuse core content.

## Problem

Found while implementing BITB-185. The fallback violence patterns (en `\bkill\b`, `\battack\b`,
`\bweapon\b`, `\bgun\b`; es/pt `\bmatar\b`; fr `\btuer\b`; ...) are bare words, so "How did David
kill Goliath?" is blocked with `keyword_violation:violence (fallback)` when ML moderation is unavailable.

## Functional requirements

- In `ContentSafetyService._full_keyword_fallback` step (e) (no self-harm), a violence match is
  dropped only if ALL hold: (1) it is a *soft* narrative-capable term (kill/murder/attack/shoot/stab
  verbs and nouns, generic weapon/gun) in en, it, de, es, fr, pt, ar; (2) a biblical anchor (character,
  place, commandment phrase, Bible framing, or a registry-derived narrative book name) is in the same
  sentence; (3) NO intent override (first-person intent, how-to, personal target, acquisition,
  imperative) matches anywhere in the message.
- Hard terms (bomb, explosive, terror, grenade, molotov, IED, napalm, ricin, anthrax, sarin,
  mass/school shooting, attentat/atentado, esplosi, sprengstoff/sprengsatz, tiroteo/tiroteio,
  fusillade, ar قنبلة/متفجر/إرهاب/تفجير/ناسف) are never exempt. Anything not in the soft list is hard.
- Steps (a) directed harm and (b) self-harm handling are unchanged (self-harm + violence word stays the
  crisis block, deliberately).

## Non-functional requirements

- All 11 UI languages tested (the allowed cases run under every UI language); ru/zh/hi/ko need no
  exemption (their BITB-198 tables already require intent).
- Fail closed: any ambiguity keeps the block. Pure regex, no extra latency (<1 ms).
- Tables live in `MultiLanguageContentFilter` (`api/utils/security.py`); book-name anchors are derived
  from `translation_registry.py`, not hardcoded.

## Approach

`MultiLanguageContentFilter.drop_narrative_violence(normalized, matches)` with
`NARRATIVE_SOFT_VIOLENCE_PATTERNS` (verbatim subset of `VIOLENCE_PATTERNS`),
`BIBLE_NARRATIVE_ANCHORS` / `BIBLE_NARRATIVE_PHRASES` (+ registry names) and
`NARRATIVE_INTENT_OVERRIDE_PATTERNS`, called from step (e) of `_full_keyword_fallback`.

## Acceptance criteria

- [x] Bible-narrative questions (David/Goliath, Cain/Abel, Judas...) are allowed in the fallback, all 11 languages
- [x] Genuine intent phrasings ("I want to build a bomb", "how do I kill someone") still block
- [x] Narrative + intent in one message ("How did David kill Goliath? I want to kill my neighbour") still blocks, in 7 languages
- [x] Hard terms next to a biblical anchor still block
- [x] Self-harm handling unchanged ("I want to die. How did David kill Goliath?" stays the crisis block)
- [x] Async path: narrative question never consults the second-opinion classifier

## Out of scope

- Exempting violence words in the self-harm path (step b) or in Llama Guard / OpenAI moderation.
- Narrative exemption for ru/zh/hi/ko (no soft bare terms there) and for `ar` outside the Arabic UI language.
- Inflected forms of the soft verbs (ucciderò, mataré, ...) -- a pre-existing gap of the violence tables, to be filed separately.
- "Kill: what does it mean in Exodus 20:13?" (bare term, anchor in the next clause) still blocks (fail closed).

## Hardening after verification (structural rules)

- Clauses split on `. ! ? ; : , newline`, dashes and Arabic/CJK punctuation (a colon/comma between digits is a verse
  reference, not a boundary). The biblical anchor must be in the SAME clause as the soft term.
- A soft VERB at the start of its clause (after "please", "and", ...) is an imperative, never exempt
  ("Tuer le maire comme David ...", "David killed Goliath, kill the mayor"). Soft nouns (murder, weapon, ...) are exempt from this rule.
- Arabic: `قتل` preceded by a prefix letter (اقتل, يقتل, لنقتل) is not plain past tense and is never exempt;
  only a bare word, a conjunction prefix (و/ف) or "لا ت" (commandment) passes.
- Intent overrides added: should/must/have to, "should we ...", let's, help me, "told me to", modern targets
  (mayor, president, principal, teacher, boss, neighbour, police, infidels, school ...), "need a gun", "gun to shoot",
  Arabic imperative / يجب / علينا, and the it/de/es/fr/pt "should we" forms.
- "Israel" and its translations are no longer anchors (modern-ambiguous); other modern-ambiguous names remain.

## Risks

- A crafted message can add an anchor ("David ... kill the mayor") without any intent phrase the
  overrides know; the overrides are a deny-list and are not exhaustive. Only applies while ML moderation is down.
- Names such as "Abel", "Joshua", "Peter", "Jericho" are also modern names/places and still count as anchors.
- False positives (fail closed): a clause split between the anchor and the verb ("Why did Cain, out of jealousy, kill his
  brother?"), a clause-initial infinitive used as a topic ("Tuer est-il un péché ?"), and present-tense Arabic narrative
  ("لماذا يقتل شاول داود").
- Clause splitting is regex-based; an abbreviation period ("1. Mose") also splits and fails closed.

## Follow-ups

_To be filed when the PR merges (see Backlog Hygiene)._
