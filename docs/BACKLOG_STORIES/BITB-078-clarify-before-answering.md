# BITB-078: Ask Before Answering — Clarify a Vague Request Instead of Guessing

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (1–2 days, prompt work + eval)
**Created:** 2026-07-25

## User Story

**As a** user who types something short and raw like "I'm lost" or "pray for me",
**I want** the companion to ask me one gentle question about what I'm facing,
**so that** the answer I get speaks to my actual situation instead of being a generic verse dump
aimed at whatever the model guessed.

## Why

The current flow always produces a full answer on the first turn, whatever it was given. For a
three-word message the pipeline still runs semantic search, picks verses, and generates a
confident, complete pastoral response — built on an assumption the user never made. That is the
single worst failure mode for this product: it *sounds* caring while addressing someone else's
problem, and the user usually just leaves rather than correcting it.

A companion sitting next to you would ask. This story makes the app do that.

The instruction technically already exists and is not working hard enough. `api/chat/prompts.py`
(`SYSTEM_PROMPT_TEMPLATE`, section **"## When the Request Is Unclear"**) says:

> If the user's message is too short or vague to understand what they are facing or asking, do not
> guess. Respond with warmth and ask one gentle clarifying question (in their language) so you can
> understand them before offering scripture.

It is buried between the scripture-weaving rules and "## Your Role", whose step 2 —
*"Ground them in scripture: bring in a fitting verse"* — reads as unconditional and pulls the model
straight back to answering. The per-intent addenda reinforce that: `COMFORT_SEEKING_PROMPT` and
`CURIOSITY_PROMPT` (`prompts.py:649-678`) both instruct the model to share scripture immediately.
And structurally, by the time the LLM is called, the scripture context block has *already* been
retrieved and injected (`api/chat/service.py:514`, `:1255`), so the model is looking at a pile of
verses while being asked to consider not using them.

## Current Behaviour

- `_detect_intent` (`api/chat/service.py:168-193`) classifies each message into
  `COMFORT | GUIDANCE | CURIOSITY | VERSE_LOOKUP | OFF_TOPIC | GENERAL`
  (`detect_intent_prompt`, `prompts.py`). There is **no "needs clarification" outcome** —
  a vague message falls into `GENERAL` or `COMFORT` and proceeds to a full answer.
- Scripture search runs before generation; the context block is prepended to the system prompt
  (`service.py:1453-1455`).
- Conversation history is carried (`request.conversation_history`, summarized by
  `build_conversation_context`, `prompts.py:608-634`, last 6 messages, 200 chars each), so a
  multi-turn clarify → answer exchange is already supported by the transport — nothing new is
  needed there.

## Proposed Behaviour

**1. Make "ask first" a first-class outcome of intent detection.**
Add a `NEEDS_CLARIFICATION` category to `detect_intent_prompt`, with explicit criteria so it stays
rare and predictable. Ask only when the message genuinely under-determines the answer:

- very short and non-specific ("help", "I'm lost", "pray for me", "verse please"), **or**
- names an emotion or event with no indication of what kind of help is wanted, **or**
- is ambiguous between materially different readings (e.g. "should I leave?" — a job? a marriage?
  a church?).

Do **not** ask when:

- the message already names a situation *and* a need ("my mother died last week, I can't pray"),
- it is a verse or passage lookup (`VERSE_LOOKUP`) — that is unambiguous by construction,
- it is a follow-up in an existing conversation where the context is already on the table,
- the safety pipeline flagged `compassionate_response_needed` — someone in crisis gets support
  first, never an interrogation. This exclusion is **non-negotiable**; see
  `COMPASSIONATE_RESPONSE_ADDENDUM` in `prompts.py`.

**2. Cap it at one clarifying turn.** If the user's reply is still vague, answer with the best
reading available and say what was assumed ("I'll speak to X — tell me if you meant something
else"). Never two questions in a row; never a question in the second turn if one was already asked.
Enforce this from `conversation_history`, not from model goodwill.

**3. Make the clarifying turn cheap and coherent.** When the intent is `NEEDS_CLARIFICATION`,
skip semantic scripture search entirely and use a dedicated short prompt
(`CLARIFICATION_PROMPT`). This is both correct — no verse should be picked for a question that
hasn't been understood — and faster and cheaper than a full turn. The clarifying reply should:
acknowledge the feeling in one sentence, ask exactly **one** open question, in the user's language,
under ~40 words, with no verse citation and therefore no `<!-- VERSES: -->` comment.

**4. Offer the clarification as tappable options where possible.** The question lands much better
with 2–3 one-tap choices ("about grief" / "about a decision" / "something else") than as an open
prompt on a phone keyboard. This shares its delivery mechanism with **BITB-080** (follow-up
buttons) — build one chip mechanism, use it for both.

**5. Strengthen the prompt itself.** Move the clarify rule out of the middle of the template into
the ordered "## Your Role" list as an explicit step 0 ("understand before you answer"), and
condition step 2 ("ground them in scripture") on having understood the request.

## Acceptance Criteria

- [ ] A vague opening message ("I'm lost", "help me", "pray for me") produces a warm, one-question
      reply with no verse citation.
- [ ] The clarifying turn skips semantic search — verifiable in the stage timings
      (`docs/HOW-TO-READ-CHAT-STAGE-TIMINGS.md`) and measurably faster than a normal turn.
- [ ] The user's answer to the clarifying question produces a full, grounded response that visibly
      uses both turns.
- [ ] At most one clarifying question per conversation.
- [ ] A specific opening message is **never** met with a clarifying question — no regression to
      "what do you mean?" for a well-formed request.
- [ ] A message flagged `compassionate_response_needed` is never met with a clarifying question.
- [ ] `VERSE_LOOKUP` and prayer lookups are never met with a clarifying question.
- [ ] Behaviour holds across languages — verified at minimum in en, it, de, es (the clarifying
      question must be in the user's language).
- [ ] Clarification rate measured and logged (new `intent` value in the existing intent logging,
      `service.py:192`), so the rollout can be judged rather than guessed at.

## Tests to Add

- `api/tests/` — intent classification: a table of vague vs. specific messages asserting the
  `NEEDS_CLARIFICATION` boundary, including the exclusions (verse lookup, crisis flag, follow-up
  turn).
- Service test: `NEEDS_CLARIFICATION` short-circuits scripture search (search provider not called)
  and emits no `verses_cited`.
- Service test: a second vague message in the same conversation answers rather than asking again.
- **Golden-set / eval:** add vague-opening cases to the retrieval-eval harness
  (`docs/SEARCH_EVAL_HOWTO.md`, **BITB-051**) so this is measured across model changes, not
  spot-checked once.

## Files Likely to Change

| File | Change |
|---|---|
| `api/chat/prompts.py` | `NEEDS_CLARIFICATION` category; new `CLARIFICATION_PROMPT`; restructure "Your Role" |
| `api/chat/service.py` | Route the new intent: skip search, use the clarification prompt, one-question cap from history |
| `api/tests/` | Intent boundary + routing tests |
| `frontend` / `android` | Render clarification options as chips (shared with BITB-080) |

## Risks

- **Over-asking is worse than the current behaviour.** A user who wrote a clear message and gets
  "can you tell me more?" will leave. The eval set and the logged clarification rate exist to catch
  this; consider shipping behind a config flag and watching the rate before making it the default.
- **Extra latency on the path to a real answer** — mitigated by making the clarifying turn skip
  retrieval, and by offering tappable options rather than requiring typing.

## Related

- **BITB-075** — a 500-character limit gives users room to be specific in the first place.
- **BITB-080** — follow-up chips; same UI mechanism, opposite end of the turn.
- **BITB-045** — typo-tolerant queries with clarification fallback (adjacent trigger, same UX).
- **BITB-018 / BITB-050** — query understanding and response depth.
