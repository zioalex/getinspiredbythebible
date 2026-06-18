# BITB-050: Improve Verse Search Thematic Relevance and Response Depth

**Status:** 🚧 In Progress
**Priority:** P1 (High) — directly improves answer quality for every user
**Size:** S (< 4 hours)
**Created:** 2026-06-12

## User Story

As a user seeking spiritual guidance, I want the verses surfaced for me to match the
*theme* of what I'm actually facing, and I want the reply to genuinely unfold that
scripture rather than drop a one-line quote — so that the answer meets me where I am.

## Problem

Two prompt-level quality gaps, both independent of the retrieval plumbing:

1. **Query expansion drifts off-theme.** The LLM expansion prompt in
   `api/chat/service.py:_expand_query` asks for emotions, themes, synonyms, *and* life
   situations as an open-ended list. In practice this over-expands: scattered, loosely
   related terms get embedded alongside the real theme and pull in irrelevant verses
   (the same failure mode behind the original frustrated-Italian-user → Job 21:27
   incident). The expansion needs to stay anchored to the one or two themes actually
   present.

2. **Replies are too shallow.** The main conversational system prompt
   (`SYSTEM_PROMPT_TEMPLATE`) tells the assistant to be warm and weave scripture in, but
   nothing asks it to *unfold* the verse. The result is often a single sentence plus a
   bare quotation, which feels thin for someone seeking comfort or guidance.

## Scope

In scope (prompt-only changes):

- **Expansion-prompt theme improvements** — rewrite the `_expand_query` prompt to
  identify the central theme(s) first, stay anchored to them, and explicitly warn
  against off-theme drift.
- **Response-depth prompt instruction** — add guidance to the main conversational
  system prompt asking for a complete, considered reply (acknowledge → offer verse →
  briefly unfold → bring home), while guarding against padding so "depth" never becomes
  "length".

Out of scope:

- The query-expansion / hybrid-search **flag flip and validation** — owned by
  **BITB-043**. This story only changes prompt *content*; it does not enable any flag.
- Topic boosting / `verse_topics` population — **BITB-044**.
- Retrieval-algorithm changes (reranking, multi-vector, etc.).

## Approach

1. Rewrite `expansion_prompt` in `api/chat/service.py:_expand_query` to be
   theme-focused: pick the 1–2 core themes, map them to closely related biblical
   themes/vocabulary, and prefer depth-on-theme over breadth. Behaviour stays
   fail-open and within the existing 100-word / `max_tokens=150` budget.
2. Add a `RESPONSE_DEPTH_GUIDANCE` constant in `api/chat/prompts.py` and append it in
   `get_system_prompt()` (alongside `BIBLE_VERSION_GUIDANCE` and
   `SCRIPTURE_FIDELITY_GUIDANCE`). It applies to the conversational prompt only — the
   verse- and prayer-lookup prompts already prescribe their own depth structure.
3. Tests: assert the expansion prompt is theme-focused and cautions against drift;
   assert the depth guidance is present in every supported language and that it forbids
   padding and allows short answers when appropriate.

## Acceptance Criteria

- [x] Expansion prompt steers the LLM to the central theme(s) and explicitly warns
      against off-theme drift / irrelevant verses.
- [x] `RESPONSE_DEPTH_GUIDANCE` added and wired into `get_system_prompt()` for all
      supported languages, without regressing existing guidance blocks.
- [x] Depth guidance asks for substance (acknowledge → verse → unfold → apply) while
      forbidding padding and allowing shorter replies for brief factual questions.
- [x] Tests cover both changes.
- [ ] Full backend test suite passes in CI.

## Files / Config

| Item | Location |
|---|---|
| Query expansion prompt | `api/chat/service.py` (`_expand_query`) |
| Response-depth guidance | `api/chat/prompts.py` (`RESPONSE_DEPTH_GUIDANCE`, `get_system_prompt`) |
| Expansion tests | `api/tests/test_chat_service_expansion.py` |
| Prompt tests | `api/tests/test_chat_coverage.py` |

## Related

- **BITB-043** — owns the query-expansion flag flip + validation (this story only edits
  the prompt text the feature uses).
- **BITB-018** — parent search-quality story.
- **BITB-044** — topic boosting / `verse_topics` population.
- Origin: GitHub issue #733 ("Story 6"), moved to the backlog per AGENTS.md → Backlog
  Hygiene.
