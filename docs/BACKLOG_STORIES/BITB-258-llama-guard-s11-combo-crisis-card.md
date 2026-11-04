# BITB-258: Crisis Card for Llama Guard S11 Combined with Other Categories

**Status:** 🔄 In Review
**Priority:** P1
**Size:** S
**Created:** 2026-10-29
**Prompted by:** BITB-255 verification (2026-10-29)

## Problem (verified in code)

`api/providers/llama_guard.py` treats a message as help-seeking only when the violated categories
are exactly `["S11"]`. S11 together with another category maps to a different reason:

- S11 + S10 → `hate_speech_detected`
- S11 + S6 (specialized advice) → `unsafe_content_detected`

`classify_crisis` (`api/utils/crisis_resources.py`) returns no card for those reasons. So a message
such as "how many pills would kill me", if Llama Guard flags it S11 + S6, is blocked with a generic
reply and **no crisis numbers**.

## Acceptance criteria

- [x] The Llama Guard result exposes its violated S-categories on the safety outcome
- [x] `classify_crisis` returns `self_harm` whenever S11 is among them, whatever the other categories
- [x] The blocked reply for these cases uses the self-harm template, not the generic one
- [x] Tests cover the S11+S6 and S11+S10 combinations on both the blocking and streaming chat paths
