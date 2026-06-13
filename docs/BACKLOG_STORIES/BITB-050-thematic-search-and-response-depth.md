# BITB-050: Improve Thematic Verse Search & Response Depth for Specific Questions

**Status:** 🎯 Todo
**Priority:** P1 (High) — answer quality on nuanced study questions
**Size:** S (< 4 hrs) — prompt-only; flag rollout deferred to BITB-043
**Created:** 2026-06-12
**Source:** Beta tester feedback (Oliver Osthoever, 2026-06-12)

## User Story

**As a** user asking a precise study question,
**I want** related verses chosen by theme (not just keywords) and an answer that engages the
specific point I raised,
**so that** I get a substantive, on-target response — like the Perplexity answer the tester compared
against.

## Problem

The tester asked about **Amos 7:1** and explicitly flagged the nuance that the locusts came *after*
the king's spring harvest, so only **the people's** subsistence crop was destroyed, not the king's
tribute. The app's answer gave a generic overview and **never engaged that point**. The tester also
observed the related-verses panel "seems to search by keywords, not thematic agreement."

Two contributing factors:

1. **Query expansion is gated off** (`api/config.py` `query_expansion_enabled` defaults `False`),
   so the embedding query is the raw user text — narrower thematic reach. **Enabling/validating this
   flag is already owned by BITB-043** (see below) and is **out of scope here**.
2. The expansion prompt (`_expand_query`) emphasises emotional/devotional themes and does not capture
   socio-economic / prophetic-justice or OT-narrative themes.
3. The system prompt does not instruct the model to address the user's specific focal point first.

## Scope Boundary vs. BITB-043

- **BITB-043** owns the *enablement + A/B validation* of `query_expansion_enabled` (and hybrid
  search). **This story does not flip that flag.**
- **BITB-050** owns the *content quality* of the expansion prompt and the *response-depth* system
  prompt instruction — improvements that help whenever expansion is on (under BITB-043) and that also
  improve direct answers regardless of retrieval.

## Approach

1. **Expansion prompt** (`api/chat/service.py` `_expand_query`): add guidance to include
   social-justice / inequality / prophetic-judgment themes when relevant, and the key theological
   themes of a named passage (e.g. Amos → prophetic indictment, justice, divine judgment). Raise the
   word cap 100 → 120.
2. **System prompt** (`api/chat/prompts.py`): add an "Addressing the User's Specific Focus"
   instruction — engage the specific detail directly and first. (Shared with BITB-045.)

## Acceptance Criteria

- [ ] For the Amos 7:1 question, the answer explicitly explains the king's spring shearing was taken
      first, so the locust plague fell only on the people's second (subsistence) crop.
- [ ] When expansion is enabled (via BITB-043), an Amos justice query surfaces prophetic-justice
      passages (e.g. Amos 2:6-7, 5:11-12) rather than generic catastrophe verses.
- [ ] No change to the default value of `query_expansion_enabled` in this story (owned by BITB-043).
- [ ] Expansion-prompt unit tests updated for the new guidance/word cap.

## Files / Config

| Item | Location | Change |
|---|---|---|
| Expansion prompt | `api/chat/service.py` `_expand_query()` | add justice/passage-theme bullets; 100→120 words |
| Response-depth instruction | `api/chat/prompts.py` `SYSTEM_PROMPT_TEMPLATE` | add "Addressing the User's Specific Focus" |
| Flag (NOT changed here) | `api/config.py` `query_expansion_enabled` | owned by **BITB-043** |

## Testing

- `api/tests/test_chat_service_expansion.py` — assert the expansion prompt includes the
  justice/passage-theme guidance; existing mocked-LLM tests stay green.
- Manual: run the Amos 7:1 German query and confirm the nuance is addressed.

## Related

- **BITB-043** — Validate & Enable Phase-1 Search (owns the `query_expansion_enabled` rollout).
- **BITB-045** — shares the "address the user's specific focus" prompt instruction.
- `docs/EMBEDDINGS_IMPROVEMENT_STRATEGY.md`.
