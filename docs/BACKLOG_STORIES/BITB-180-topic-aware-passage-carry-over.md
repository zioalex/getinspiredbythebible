# BITB-180: Topic-Aware Passage Carry-Over for Follow-Up Turns

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M
**Created:** 2026-10-10
**Prompted by:** BITB-178 follow-up (PR #1145, Notes).

## Problem

BITB-178 FR2 re-grounds a follow-up that names no verse by re-fetching the passage referenced in
the last `passage_context_history_lookback` (4) history messages
(`ChatService._history_references`, `api/chat/service.py`). It does not check whether the follow-up
is still about that passage. A user who discussed Luke 1:79 and then asks "what does the Bible say
about anxiety?" still gets Luke 1:72–81 in the prompt, labelled "the passage discussed earlier …
re-read it before answering the user's follow-up". That can pull the new answer back toward Luke 1
and costs one extra range query per turn.

## Functional Requirements

- FR1 Carry the earlier passage only when the follow-up is plausibly about it. Candidate signals, in
  order of cost: (a) the existing intent / topic detection already run on the turn (a new
  topical search intent → no carry-over); (b) short challenge/clarification turns ("are you sure?",
  "who?", "why?") → carry-over; (c) embedding similarity between the follow-up and the earlier
  passage above a threshold. Pick the cheapest that meets the acceptance criteria; decide in Plan.
- FR2 Keep the BITB-178 behaviour for the reported case: a bare "bist du sicher…?" after the Luke
  1:79 answer must still carry the passage.
- FR3 Behind a setting, default on, so it can be turned off without a deploy if it hurts the live
  pass rate.

## Acceptance Criteria

- [ ] An unrelated topical follow-up gets no carried-over passage (11 languages, both chat paths)
- [ ] The BITB-178 pushback cases (all 11 languages) still get the passage; the `interpretation`
      golden set does not regress in the weekly live run (`golden-set-live.yml`)
- [ ] New golden-set cases for "topic switch after a verse discussion" in en/de/it
- [ ] Setting documented in `config.py` and `scripts/env-manifest.yaml`; flag-off equals BITB-178

## Open Questions

- Which signal (FR1 a/b/c)? Decide from the live runs: if they show no harm from the current
  behaviour, this story may be cancelled.
