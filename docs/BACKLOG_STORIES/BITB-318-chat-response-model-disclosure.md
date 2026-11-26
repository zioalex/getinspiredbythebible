---
id: BITB-318
status: todo
priority: P3
kind: nfr
size: M
rank: 50
created: 2026-11-15
---

# BITB-318: Chat Responses Still Name the LLM Provider and Model to Anonymous Clients

**Prompted by:** BITB-307 verification (follow-up). BITB-307 removed provider and model
from the public `GET /config` because "the model name tells an attacker which jailbreaks to
try" — but every chat response still carries them.

## Problem

- `ChatResponse` (`api/chat/service.py`, `class ChatResponse`) and the SSE `metadata` event
  return `provider` and `model` on every `POST /api/v1/chat` and `/api/v1/chat/stream`.
- Clients read them: web `ChatIsland.tsx` (stores `provider`/`model` on the message and sends
  `model_used` with feedback), Android `ChatResponseDto.kt` and `EventSourceParser.kt`.
- So the BITB-307 `/config` trim does not actually hide the model from an attacker.

## Decision needed (owner)

Either (a) accept the disclosure (feedback attribution needs the model) and close this story,
or (b) replace the public fields with an opaque server-side identifier (e.g. a short
`model_ref` hash the backend resolves when it stores feedback) and keep the real name in
logs and the admin config.

## Requirements (if b)

- Backend stops emitting `provider`/`model` in chat responses and SSE metadata; emits an
  opaque `model_ref`; feedback accepts `model_ref` and resolves it server-side.
- Web and Android updated in the same PR; older app versions keep working (fields become
  optional/defaulted on both sides — Android DTOs already default to `""`).
- Tests on all three platforms; feedback attribution still records the real model.

## Acceptance criteria

- [ ] Owner decision recorded (a or b)
- [ ] If (b): no chat response body contains the provider or model name

## Related

BITB-307 (trimmed `/config`), feedback model attribution.
