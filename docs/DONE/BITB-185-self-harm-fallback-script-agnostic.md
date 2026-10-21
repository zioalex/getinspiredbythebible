# BITB-185: Self-Harm Fallback — Script-Agnostic Matching and Precedence

**Status:** ✅ Done — PR #1166 merged 2026-10-13
**Size:** M (re-scoped 2026-10-13: second-opinion classifier)
**Created:** 2026-10-10

**As a** user in crisis, **I want** the keyword fallback to recognise my message regardless
of detected language or phrasing, **so that** I get the compassionate response.

## Problem

Found while verifying BITB-183 (`ContentSafetyService._full_keyword_fallback`):

1. It only checks `[language, "en"]`. Short or mismatched-script messages whose language is
   detected as `en` skip the ru/zh/hi/ko/ar self-harm patterns.
2. Violence patterns run before self-harm, so fr "je veux me tuer" and pt "me matar" are
   blocked as violence instead of taking the compassionate path.

## Acceptance criteria

- [x] The fallback runs every language's self-harm regex, independent of the detected language
- [x] First-person self-harm phrases take precedence over violence matches (directed harm still blocks)
- [x] Parametrized tests across all 11 languages, including mismatched language/script cases

## Spec v2 — second LLM opinion for ambiguous self-harm vs violence (2026-10-13)

**Guiding principle (owner):** always support people in need, without compromising the
security of others.

Two verifier passes showed that no keyword precedence rule is safe on its own: self-harm-first
lets "I want to die. How do I build a bomb to attack my school?" through, violence-first blocks
crisis users who mention a method, and a bare-term list ("suicide bomb") never covers every
script (ar انتحارية, zh 自杀式炸弹).

**Owner decisions:**

1. The second opinion comes from the **main chat LLM provider** (`LLM_PROVIDER`), which is
   independent of the Llama Guard / OpenRouter path that has already failed when the fallback runs.
2. It runs **only on ambiguous fallback cases**: a self-harm match AND a violence keyword that
   lies outside every self-harm match span ("kill" inside "kill myself" does not count).
3. On a `BOTH` verdict, an unparseable answer, a timeout, an error, or the feature being
   disabled: **block and show the crisis-resources message** (`self_harm_blocked` template).
   The harmful request is never answered; the person in crisis still gets help.

### Functional requirements

- FR1 Directed harm / hate speech in any language -> block (unchanged, deterministic, no LLM).
- FR2 Self-harm only (no violence outside the self-harm spans) -> compassionate path (no LLM).
- FR3 Violence only -> block as violence (scope `[language, "en"]`, unchanged).
- FR4 (refined 2026-10-13 per owner principle: support people in need without compromising others' security) Ambiguous -> classifier returns exactly one of `SELF_HARM`, `HARM_TO_OTHERS`, `BOTH`,
  `NEITHER`. `SELF_HARM` -> compassionate; `HARM_TO_OTHERS` -> crisis block (refused, helpline shown); `BOTH`,
  `NEITHER` (keywords fired on both, so not trusted as clean), or anything else -> crisis block.
- FR5 For deciding ambiguity, violence keywords are checked in every language (script-agnostic),
  so mixed-script terrorism phrasing is caught; the plain violence block keeps its narrow scope.
- FR6 The `self_harm_blocked` crisis message exists in all 11 languages (ru, zh, hi, ko added).
- FR7 Prompt-injection hardening: the user text is passed as delimited data, the answer is
  parsed strictly (exact label only), and anything else is treated as a failure (crisis block).

### Non-functional requirements

- Only ambiguous fallback messages pay the extra LLM call; timeout
  `CONTENT_SAFETY_SECOND_OPINION_TIMEOUT` (default 3s), temperature 0, a few output tokens.
- Feature flag `CONTENT_SAFETY_SECOND_OPINION_ENABLED` (default true); disabled -> crisis block.
- Metric for verdicts (including timeout/error) so the path is observable; logs carry a text
  hash only, never the raw message.
- All 11 languages covered by parametrized tests.

### Acceptance criteria (v2)

- [x] Self-harm + method words only (gun, weapon, knife): classifier `BOTH` / down -> crisis
      block; `HARM_TO_OTHERS` -> crisis block
- [x] "How do I make a suicide bomb", ar "كيف أصنع قنبلة انتحارية" and "I want to die. How do I
      build a bomb to attack my school?" block in every classifier outcome (hard-violence rule);
      native zh 如何制作自杀式炸弹, ko, ru, hi bomb phrasing is caught too
- [x] "I want to kill myself" / fr "je veux me tuer" / pt "quero me matar" stay compassionate
      without an LLM call
- [x] "I am thinking about suicide, I want to kill myself with a gun": classifier `SELF_HARM`
      -> compassionate; classifier down -> crisis block (never a plain violence refusal)
- [x] Junk, injected or late classifier answers -> crisis block
- [x] Crisis block message localized in all 11 languages
- [x] End-to-end tests through `check()` with Llama Guard down and a mocked chat LLM

### Out of scope

- Pattern-table phrasing gaps (BITB-186), stage-1 language scoping (BITB-193), Bible-narrative
  violence false positives (BITB-194).

## Implementation notes (v1)

- `MultiLanguageContentFilter.find_self_harm(normalized, preferred=None)` tries the detected
  language first, then every other language's self-harm regex; returns `(language, matched_text)`.
  `find_directed_harm(normalized)` checks every language's directed-harm regex plus hate speech.
  Pattern tables and `check_multilingual` are unchanged (pattern gaps stay with BITB-186).
- `_full_keyword_fallback` order is now: (a) directed harm / hate speech in any language -> block
  (`keyword_violation:directed_harm (fallback)` / `:hate_speech (fallback)`); (b) self-harm in any
  language -> compassionate result (logs `matched_language`); (c) violence scoped to
  `[language, "en"]` -> block; (d) clean.
- (v1, superseded by v2) Self-harm now wins over plain violence keywords ("I want to kill myself with a gun" is
  compassionate). Trade-off: a mixed "kill him then myself" message without directed-harm phrasing
  is treated as help-seeking (decision tracked in BITB-195).
- (v1, superseded by v2) The bare-noun exception (`_BARE_SELF_HARM_TERM`) was removed; ambiguity
  handling below replaces it.
- Known limitation: `find_directed_harm` runs every language's directed-harm regex, so single
  words from other languages give false positives in the fallback (it "Gioco della morra", pt
  `\bmorra\b`, it `\bmuori\b`, fr `\bcrève\b`, es `\bmuérete\b`). Documented, not fixed
  (see BITB-193).
- Tests: `api/tests/test_self_harm_keyword_fallback_languages.py` gains first-person overlap,
  11-language x phrase cross-products (crisis and benign), 15 mismatched language/script cases,
  directed harm x 11 codes, plain violence, and three end-to-end `check()` tests with ML moderation
  down.

## Implementation notes (v2)

- `security.py`: `find_all_self_harm_spans` (finditer over every language) and
  `find_violence_matches(normalized, languages=None)` (all languages when `None`).
- `_full_keyword_fallback` (sync, signature unchanged): directed harm -> block; self-harm spans +
  violence matches in ALL languages minus those inside a self-harm span; self-harm only ->
  compassionate; self-harm + remaining violence -> `self_harm_with_violence (fallback)`
  (`allowed=False`, `is_help_seeking=True`, `compassionate_response_needed=False`); no self-harm ->
  violence scoped to `[language, "en"]` as before. `_map_reason_to_category` checks `self_harm`
  before `violence`, so the reason maps to the `self_harm_blocked` template (tested).
- New async `ContentSafetyService._keyword_fallback` is used by every async stage (Llama Guard,
  OpenAI moderation, Azure). On the ambiguous reason it calls
  `utils/safety_second_opinion.classify_self_harm_vs_violence` (main `LLM_PROVIDER`, temperature 0,
  `max_tokens=16`, `asyncio.wait_for` with `CONTENT_SAFETY_SECOND_OPINION_TIMEOUT`, text wrapped in
  a random per-call `<message-{nonce}>` tag (`secrets.token_hex`; `<`/`>` in the text replaced by
  fullwidth `＜＞` so it cannot close the tag), strict exact-label parse). SELF_HARM -> compassionate
  (`possible_help_seeking (fallback, second_opinion)`); HARM_TO_OTHERS -> crisis block (refused, helpline info; refined 2026-10-13); BOTH, NEITHER, None -> crisis block.
- Settings `CONTENT_SAFETY_SECOND_OPINION_ENABLED` (true) and
  `CONTENT_SAFETY_SECOND_OPINION_TIMEOUT` (3.0), both in `scripts/env-manifest.yaml`. Metric
  `content_safety.second_opinion_total{verdict}`; logs carry a text hash only.
- `self_harm_blocked` template gained ru, zh, hi, ko.
- Hard-violence rule (H1): new `HARD_VIOLENCE_PATTERNS` table + one compiled script-agnostic regex in
  `security.py` (`find_hard_violence_matches`; bomb, explosive, terror, attack, massacre, mass
  shooting ... in en/it/de/es/fr/pt/ar/ru/zh/hi/ko; "panic/anxiety/heart/asthma/nervous attack", "night terrors", terrorized/bombarded/bombshell and Romance "attacco/ataque/attaque de panique/ansia/cuore" excluded by a post-filter in `find_hard_violence_matches`; hi `बम` is Devanagari-boundary-guarded, zh `恐怖` only as 恐怖分子/袭击/主义/活动, ko `폭발물` not bare `폭발`; added shoot up, grenade, molotov, IED, napalm, ricin, anthrax, sarin and per-language grenade/molotov terms). A hard-violence
  term outside every self-harm span makes the fallback ambiguous even where the old violence tables
  have no entry (ru/zh/hi/ko), and `_keyword_fallback` then returns the crisis block WITHOUT
  calling the classifier (counter verdict `hard_violence`). The classifier may only override to
  compassionate when the remaining violence terms are method words (gun, weapon, kill, arma ...).
  Classifier errors log the exception class name only.
- Tests: `api/tests/test_safety_second_opinion.py`; v1 expectations updated in
  `test_self_harm_keyword_fallback_languages.py`.

- Verifier round 4: context exclusions in `find_hard_violence_matches` now apply only to the
  ambiguous word itself ("attack" after panic/anxiety/heart/asthma/nervous, exact "terror(s)"
  after "night"), with a leading word boundary, so "nervous bombing", "night terrorists" and
  "sweetheart bombs" still count. "shoot up again" is no longer excluded. Added zh 恐怖份子 / 恐攻
  and ko 폭발시키/킬/켜. Regression tests assert both directions (exclusion alone is clean,
  exclusion + real hard term blocks).

## Follow-ups

- BITB-193: stage-1 `check_multilingual` directed-harm check limited to the detected language
- BITB-194: fallback violence regex blocks Bible-narrative questions when ML moderation is down
- BITB-195: cancelled, decided and implemented in v2
- BITB-196: murder-suicide elliptical phrasing ("...and my family") takes the compassionate path
- BITB-197: violence/hate/directed/sexual/generic blocked templates lack ru/zh/hi/ko
- BITB-198: ru/zh/hi/ko have no native violence patterns in the fallback (pre-existing)
- BITB-199: classifier uses the primary model only; reasoning models likely unparseable
