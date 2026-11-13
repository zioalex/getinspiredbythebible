# BITB-075: Raise the Chat Message Limit to 500 Characters (and Make It a Single Source of Truth)

**Status:** 🎯 Todo
**Priority:** P1
**Size:** S (< 4 hrs)
**Created:** 2026-07-25

## User Story

**As a** user describing a real, complicated situation,
**I want** to write up to 500 characters in one message,
**so that** I can give enough context to get a useful answer instead of having to amputate my
question to fit an arbitrary 300-character box.

## Why

300 characters is roughly three sentences. The people this app is for — someone in grief, someone
facing a hard decision — routinely need more than three sentences to say what is actually going on.
Truncating them costs exactly the context the retrieval and the LLM need to answer well (which is
also what **BITB-078** is about: better context in, better answer out).

**A second problem surfaces while doing this.** The limit is currently hard-coded in *five* places
that already disagree with each other:

| Layer | Value | Location |
|---|---|---|
| Backend default | **300** | `api/config.py:180` |
| **Deployed production value** | **200** | `deployment/terraform.tfvars:91` (→ `MAX_MESSAGE_LENGTH` env var via `deployment/main.tf:107-108`) |
| Terraform variable default | **200** | `deployment/variables.tf:404-408` |
| Env manifest default | **200** | `scripts/env-manifest.yaml:154-157` |
| Web client | **300** | `frontend/src/lib/api.ts:121` |
| Android client | **300** | `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt:173` |

So in production today the server rejects at **200** while both clients happily let the user type
**300** and display "max 300 characters" in the error. A 250-character message is accepted by the
input box, sent, rejected with HTTP 422, and reported back to the user with a limit number that is
wrong. Raising the number without fixing the drift just moves the bug.

## Current Behaviour

- `api/chat/service.py:95` — `message: str = Field(..., min_length=1, max_length=settings.max_message_length)`;
  over-length messages produce a 422 whose `detail[].msg` reads
  `String should have at most N characters`.
- `frontend/src/lib/api.ts:118-121` — `MAX_MESSAGE_LENGTH = 300`, documented as mirroring
  `api/config.py`, but not actually fetched from the backend.
- `frontend/src/app/[locale]/ChatIsland.tsx:1180` caps the textarea via `maxLength`; `:1208-1217`
  renders the counter from 80% of the limit; `:738` shows
  `Chat.messageTooLong` (`frontend/messages/en.json:131`) with `{max}` interpolated from the
  client constant.
- Android: `ChatViewModel.kt:173` (constant, with a comment saying it mirrors the backend),
  `ChatInputField.kt:37` (`maxLength: Int = 300` default), `ChatScreen.kt:545` (passes the
  constant), `ChatViewModel.kt:1213` (error string `error_message_too_long`,
  `android/app/src/main/res/values/strings.xml:190`).
- `GET /config` (`api/main.py:368-406`) already returns a `chat` block
  (`max_context_verses`, `max_conversation_history`) but **not** `max_message_length` — the natural
  place to publish it.

## Proposed Behaviour

1. **Raise the limit to 500** everywhere the number lives:
   - `api/config.py:180` → `max_message_length: int = 500`
   - `deployment/variables.tf:404-408` default → `500`
   - `deployment/terraform.tfvars:91` and `deployment/terraform.tfvars.example:153` → `500`
   - `deployment/README.md:804,815` table/example → `500`
   - `scripts/env-manifest.yaml:154-157` default → `"500"`
2. **Publish the effective limit** from the backend: add `"max_message_length": settings.max_message_length`
   to the `chat` block of `GET /config`.
3. **Make the clients follow the server.** Keep the hard-coded constant only as a *fallback* for
   before `/config` resolves (and bump it to 500 so the fallback is not itself a lie):
   - Web: read the value in the existing config path and thread it through `ChatIsland` (textarea
     `maxLength`, counter threshold, `messageTooLong` interpolation) instead of importing the
     constant directly.
   - Android: expose it on `ChatUiState`, seeded from `MAX_MESSAGE_LENGTH` and updated once
     `/config` is read; `ChatInputField` and the error string use the state value.
4. Verify the LLM prompt/token budget still holds at 500 characters — the message is embedded in the
   search query and the chat history summary (`api/chat/prompts.py`, history truncated at 200 chars
   per turn around `prompts.py:630`), so no prompt-size regression is expected, but it should be
   checked rather than assumed.

**Deliberately out of scope:** a fully dynamic per-locale limit, and any change to the *contact
form* message limit (a separate field with its own validation — see BITB-051/BITB-052).

## Acceptance Criteria

- [ ] A 500-character chat message is accepted end-to-end (web and Android) against a backend
      running the new default.
- [ ] A 501-character message is prevented client-side (input cap) and, if it somehow reaches the
      API, rejected with 422.
- [ ] Production configuration (`terraform.tfvars`) and the code default agree; no layer still says
      200 or 300.
- [ ] `GET /config` returns `chat.max_message_length`.
- [ ] Web and Android use the server-published value when available, and the compiled-in constant
      only as a pre-config fallback.
- [ ] The "message too long" error shows the *effective* limit, not a stale constant.
- [ ] Character counter still appears at 80% of the effective limit and turns red at the limit.

## Tests to Add / Update

- `api/tests/test_security.py:55,63` — already derives from `settings.max_message_length`; confirm
  it still passes and add an explicit 500-boundary case.
- New API test: `GET /config` includes `chat.max_message_length`.
- `frontend/src/lib/api.test.ts:1075` — the 422 fixture asserts the literal string
  `"String should have at most 300 characters"`; update, and prefer asserting on the error *type*
  rather than the copy.
- `frontend/src/app/[locale]/page.test.tsx:36` — mock currently pins `MAX_MESSAGE_LENGTH: 300`.
- Android: `ChatViewModel` test for the 500 boundary and for the error message rendering the
  effective limit.

## Files Likely to Change

| File | Change |
|---|---|
| `api/config.py` | Default 300 → 500 |
| `api/main.py` | Publish `chat.max_message_length` on `/config` |
| `deployment/variables.tf`, `deployment/terraform.tfvars{,.example}`, `deployment/README.md` | 200 → 500 |
| `scripts/env-manifest.yaml` | Default "200" → "500" |
| `frontend/src/lib/api.ts` | Fallback constant → 500; read limit from `/config` |
| `frontend/src/app/[locale]/ChatIsland.tsx` | Use the effective limit for cap, counter, error |
| `android/.../ChatViewModel.kt`, `ChatInputField.kt`, `ChatScreen.kt` | Effective limit via UI state |
| tests as listed above | Boundary + config tests |

## Risks

- **Cost/latency:** longer messages mean slightly larger embeddings and prompts. 500 chars is still
  small relative to the scripture context block; impact should be negligible but is worth a glance
  at the chat stage timings after rollout (`docs/HOW-TO-READ-CHAT-STAGE-TIMINGS.md`).
- **Abuse surface:** the limit is one of the abuse controls (BITB-061). 500 is still a tight bound;
  rate limiting and the session lifetime limit remain the primary defenses.

## Related

- **BITB-078** — clarifying questions; both stories are about getting enough context to answer well.
- **BITB-061** — fail-closed abuse controls (message length is one of them).
- **BITB-051 / BITB-052** — contact-form length/email errors (different field, same class of bug:
  client and server disagreeing about a limit).
