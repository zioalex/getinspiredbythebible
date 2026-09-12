# BITB-129: Culturally Tuned Warmth — Only When the Person Needs Support

**Status:** 🎯 Todo
**Priority:** P1 — user-reported quality gap on the product's core promise (spiritual support), and
the classifier it depends on already ships
**Size:** M (1-2 days for `it` + the gating and tests; each further locale is S)
**Created:** 2026-09-12
**Reported by:** product owner, relaying Italian users — "the answers are too cold"

## User Story

**As** someone writing to Vox Quieta about something painful, in my own language,
**I want** the reply to carry warmth the way it is carried in my culture,
**so that** it reads as a person being close to me rather than a correct but distant answer —
while a plain question about the Bible still gets the same clear, neutral answer it gets today.

## Why This Exists

Italian users report that replies feel cold. The product's value is not the information; it is
feeling accompanied. A reply can be scripturally correct, well-grounded and still fail, because
*how much closeness a comforting reply is expected to express* is culturally specific. The current
system prompt is authored once, in English, and the same register is asked for in all 11 supported
languages. English pastoral register — measured, a little reserved, structured — translated
faithfully into Italian reads distant, almost bureaucratic. The same register in German reads
roughly as intended; the same register in Italian under-delivers.

Two facts make this cheap to fix:

1. **The classification already exists.** `_detect_intent()` (`api/chat/service.py:172`) already
   labels every message `COMFORT | GUIDANCE | CURIOSITY | VERSE_LOOKUP | NEEDS_CLARIFICATION |
   OFF_TOPIC | GENERAL`, on a fast call, on by default
   (`content_filter_intent_detection: bool = True`, `api/config.py:198`). No new LLM call and no new
   latency stage are needed to know whether someone is hurting or just asking.
2. **The prompt layer already composes addenda.** `_build_messages()`
   (`api/chat/service.py:1559`) layers `COMPASSIONATE_RESPONSE_ADDENDUM`, `OFF_TOPIC_PROMPT` and
   `CLARIFICATION_PROMPT` onto the base persona instead of replacing it. A cultural-register
   addendum is the same move, one layer further.

Worth ruling out up front: Italian is **not** on a weaker model. `language_model_overrides` is unset
in every committed env template, so `it` runs the default model (`api/utils/language.py:492`). This
is a register problem in the prompt, not a model-capability problem.

## The Idea, Stated Precisely

Cultural tuning is gated on **what the person needs**, not only on **which language they wrote in**:

| Detected intent | Cultural register addendum | Rationale |
|---|---|---|
| `COMFORT` | ✅ applied | the reported gap — someone in pain |
| `GUIDANCE` | ✅ applied | a life decision, pastoral by nature |
| `CURIOSITY` | ❌ not applied | informational; today's neutral voice is correct |
| `VERSE_LOOKUP` | ❌ not applied | informational |
| `NEEDS_CLARIFICATION` | ❌ not applied | one short question; register barely applies |
| `OFF_TOPIC` | ❌ not applied | redirect is already scripted |
| `GENERAL` | ❌ not applied in v1 | a catch-all bucket; tuning it would tune everything |

So: "a question about the Bible with no problem behind it stays exactly as it is today" is enforced
in code, by intent, not left to the model's judgement — the same discipline BITB-078 used for its
clarification gate (`_wants_clarification`, `api/chat/service.py:723`).

## Proposed Design

### 1. A pastoral-register registry, keyed by locale

A new dict in `api/chat/prompts.py` next to `LANGUAGE_NAMES` / `BIBLE_OPENING_PHRASES`, mapping a
language code to a short English instruction block (English, like every other addendum, since the
base prompt already handles output language):

```python
PASTORAL_REGISTER_NOTES: dict[str, str] = {
    "it": """...Italian pastoral register: express closeness explicitly and in the first
person ... flowing prose over bullet lists ... warmth is shown, not implied ...""",
    # "de": ..., "en": ...  (added only once calibrated)
}
```

**A locale with no entry gets no addendum and therefore byte-identical behaviour to today.** This is
the central safety property of the design: we ship `it` because we have a real report from real
Italian users, and we do not invent cultural characterisations for ten languages nobody has
complained about. Each later locale is its own small story, ideally with a native-speaker review
attached.

### 2. Language is a proxy for culture — say so in the code

We know the response language (`effective_language`), not the country. `it` covers Italy and
Italian-speaking Switzerland; `pt` covers Brazil and Portugal; `es` covers two dozen countries whose
pastoral registers differ. v1 keys on the language code and the registry must be *shaped* so a
region-qualified key (`pt-BR`, `es-MX`) can be added later without restructuring. This limitation
belongs in a comment, not in a silent assumption.

### 3. Composition order and precedence

```
base persona (get_system_prompt)
  + cultural register addendum      # new, pastoral intents only
  + compassionate addendum          # safety — must come last and win
```

The crisis/self-harm path (`COMPASSIONATE_RESPONSE_ADDENDUM`, `api/chat/prompts.py:760`) keeps final
say. A register note must never soften, contradict or re-word crisis instructions; it tunes warmth,
never what is said to someone at risk.

### 4. What the addendum may and may not touch

**May:** degree of expressed closeness, first- vs third-person framing, prose vs list structure,
how directly feeling is named, formality/address conventions.

**May not:** which verse is chosen, verse fidelity, visible literal references, localized book names,
the `<!-- VERSES: -->` contract, the language rule, reply length targets. Warmth is register, not
content. Every existing grounding and citation guarantee must survive untouched — this is the main
regression risk and is an explicit acceptance criterion below.

### 5. Flag and rollout

`chat_cultural_tone_enabled: bool = False` in `api/config.py`, matching the
`chat_clarification_enabled` precedent: merged dark, enabled in prod once the Italian samples have
been reviewed by the users who raised the complaint. Cost when on: zero extra LLM calls, roughly
+80-120 system-prompt tokens on pastoral turns only.

## Scope

**In:** the gate, the registry, the `it` entry, composition in `_build_messages()`, the flag, tests,
the before/after sample pack, both the blocking and the streaming chat paths
(`api/chat/service.py` has two entry points — `chat()` ~line 444 and the streaming variant ~line
1258; a gate applied to only one of them is a bug).

**Out:** new locales beyond `it`; region-qualified locales; any per-user tone preference in the UI;
changing the intent taxonomy; `GENERAL`-bucket tuning.

## Acceptance Criteria

- [ ] `COMFORT`/`GUIDANCE` + a locale with a registry entry ⇒ register addendum present in the system
      prompt
- [ ] `CURIOSITY`/`VERSE_LOOKUP`/`NEEDS_CLARIFICATION`/`OFF_TOPIC`/`GENERAL` ⇒ addendum absent, in
      every locale
- [ ] A locale with no registry entry ⇒ system prompt byte-identical to today, at every intent
- [ ] Flag off ⇒ system prompt byte-identical to today, everywhere
- [ ] Gate applied identically on the blocking and streaming chat paths (asserted by test, not by
      inspection)
- [ ] Crisis path unchanged: with `compassionate_mode=True` the compassionate addendum is still
      present, still last
- [ ] Existing verse-grounding, citation and prompt-composition suites pass unchanged
      (`api/tests/test_verse_grounding.py`, `api/tests/test_intent_detection.py`,
      `api/tests/test_chat_coverage.py`)
- [ ] Sample pack: ~10 Italian pastoral prompts captured before/after, committed under
      `docs/CONTENT/` or the story folder, reviewed by at least one Italian native speaker who is
      not the author; verses still cited correctly in every "after" sample
- [ ] Outcome metric named and baselined before rollout: negative-feedback rate for `it` versus `en`
      and `de` (`feedback.language` already exists, `api/feedback/models.py:162`)

## Risks

- **Prompt bloat / instruction dilution.** Every addendum competes with the ones already there; a
  warmth note can quietly cost a citation. Mitigated by keeping the note short and by the grounding
  suites being part of the acceptance criteria.
- **Cultural stereotyping.** "Italians want effusive replies" is a caricature if written carelessly.
  The note must describe *pastoral-language conventions*, reviewed by speakers of the language —
  never national character. This is why empty-by-default matters.
- **Misclassification.** A `COMFORT` message read as `CURIOSITY` gets the cold reply anyway; this
  story does not improve the classifier, it only consumes it. If the sample pack shows the
  classifier is the real bottleneck for Italian, that is a separate story.
- **Unfalsifiable success.** "Warmer" cannot be unit-tested. The sample pack plus the per-language
  feedback metric is the honest substitute, and the reviewers should be the people who complained.

## Open Questions

1. **Is it culture, or is it translated-English register?** A competing hypothesis worth testing with
   the very same sample pack: the Italian replies may read cold because an English-authored prompt
   yields calque-y, formal Italian — in which case the fix helps *every* non-English locale and
   should be written as a general "write as a native pastoral voice, not as a translation"
   instruction rather than as per-culture notes. Cheap to check: read ten Italian baseline replies
   and ask whether they sound translated or merely reserved. **Do this before writing the `it`
   note.**
2. Should `GENERAL` be included once we have data? It likely carries some emotional traffic.
3. Does `GUIDANCE` really want cultural tuning, or mainly `COMFORT`? Start with both, split if the
   samples disagree.
4. Do we ever want the user to choose their register explicitly (a settings toggle), making this an
   inferred default rather than a fixed behaviour?
