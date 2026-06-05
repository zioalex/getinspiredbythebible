# BITB-042: Feedback "Rethink" Delay + Explicit Maintainer-Sharing Notice on Thumbs-Down

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (1-2 days)
**Created:** 2026-06-05

## User Story

**As a** person who taps thumbs-up or thumbs-down on an AI answer,
**I want** a short (~10-second) window to reconsider or undo my rating before
it is committed, and a clear, short notice — right at the moment I tap
thumbs-down — that my message will be shared with the app's maintainer,
**so that** I don't accidentally lock in the wrong reaction, and I am
genuinely aware (not just via the buried Terms of Use) that what I write in a
negative-feedback comment goes to a real person.

## Why

Two distinct concerns, both about respecting the user at the moment of feedback:

1. **No room to reconsider.** Today a thumbs-up/down is acted on the instant
   it is tapped — `ChatMessage.tsx` calls `onFeedback(rating)` on click, which
   immediately opens the feedback modal, and the buttons then lock
   (`feedbackGiven !== null` disables both). A misftap is irreversible. A brief
   "rethink"/undo window gives people a chance to correct an accidental or
   impulsive rating before anything is sent.

2. **Sharing is disclosed only in the Terms / a generic logging notice.**
   The modal shows a generic privacy line —
   `Feedback.privacyNotice`: *"By submitting feedback, your message and the AI
   response will be logged to help us improve the service."* — which says
   "logged", not "sent to a person". In reality, **thumbs-down feedback is
   emailed to the maintainer**: the backend relays negative feedback to
   `contact_notification_email` (see `api/utils/email_service.py`, and BITB-032
   which routes it to `support@voxquieta.org`). The user explicitly wants this
   stated plainly at the point of thumbs-down — *"the message will be shared
   with the maintainer of the app"* — even though it is also covered in the
   Terms of Use. People should know without having to read the legal page.

## Current Behaviour (grounding)

- **Thumbs buttons** — `frontend/src/components/ChatMessage.tsx` ~L282–315:
  `onClick={() => onFeedback("positive" | "negative")}`; both buttons disabled
  once `feedbackGiven !== null`. A "Thanks for your feedback!" label
  (`Feedback.thanks`) appears immediately after.
- **Open flow** — `frontend/src/app/[locale]/ChatIsland.tsx`:
  `handleFeedbackClick()` (~L690) sets the rating + message id and opens the
  modal synchronously; `handleFeedbackSubmit()` (~L700) POSTs via
  `submitFeedback()`.
- **Modal** — `frontend/src/components/FeedbackModal.tsx`: textarea + a single
  amber privacy notice box rendering `t("privacyNotice")`; Skip submits an
  empty comment, Submit sends the typed comment.
- **Backend** — negative feedback triggers a maintainer email
  (`api/utils/email_service.py`, recipient `contact_notification_email`);
  positive feedback is stored but (today) does not email anyone.
- **i18n** — the `Feedback` block exists in all locale files under
  `frontend/messages/` (en, de, es, fr, hi, it, ko, pt, ru, zh, ar).

## UX Direction (decided)

The goal is a **great, frictionless UX**, so the design favours an inline,
non-blocking flow over the current pop-up modal. The tap *is* the action; it
registers instantly with an Undo, and everything else (comment, notice) lives
inline and is optional. No modal interrupts the conversation.

> Pattern reference: like YouTube's like/dislike (instant, with a quiet Undo)
> and Gmail's "Message sent · Undo" — the action commits unless you reverse it,
> rather than forcing a confirmation step.

## Proposed Behaviour

### 1. "Rethink" / undo window (~10s) — both ratings

When the user taps thumbs-up or thumbs-down:

- Reflect the choice immediately in the UI (the tapped thumb fills/highlights)
  but treat it as **pending, not committed** — nothing is sent yet.
- Show an inline, non-blocking affordance with a countdown and an **Undo**,
  e.g. *"Thanks — sending in 10s · Undo"*, counting down. It appears in place,
  under the message; it does **not** block or cover the chat.
- If the user taps **Undo** (or re-taps the same thumb, or switches to the
  other thumb) within the window, cancel the pending action — no request is
  sent and the buttons return to their neutral, re-tappable state.
- **When the countdown elapses, the rating commits** (the POST is sent). That
  is the whole commit step — there is **no forced modal**.
- The window length must be a single named constant (e.g.
  `FEEDBACK_RETHINK_MS = 10_000`) so it is easy to tune.
- The countdown is shown as a **quiet progress bar** (not ticking seconds) —
  decided for least-naggy feel. Respect `prefers-reduced-motion` (no animation;
  the Undo affordance still works); the affordance must be screen-reader
  friendly (announce "Undo available", not each tick).

### When is the feedback actually sent? (one send, never twice)

The 10s window governs the **rating**; the optional comment, if opened, takes
priority over the timer. There is exactly **one** request per rating, so the
maintainer receives one email — with the comment attached if one was written.

- **No comment (common case):** a single POST fires the moment the progress bar
  completes (~10s). For thumbs-down this is what triggers the maintainer email.
- **User opens the comment field:** the countdown **pauses** (we don't pull the
  field away mid-sentence). The progress bar is replaced by an explicit
  **Send**. The rating + comment are sent together when they tap Send (or blur
  the field with non-empty text). Still one request, one email.
- **Undo / re-tap / switch** before either of the above → nothing is sent and
  no email is generated.

This avoids a "rating now, comment later" double-send and guarantees the
maintainer email carries the comment when there is one.

### 2. Optional inline comment (replaces the forced modal)

- The comment is **optional and inline**, not a modal. On thumbs-down, reveal a
  small, dismissible inline comment field next to the Undo affordance
  (*"Add a comment (optional)"*). On thumbs-up, the same optional field with a
  positive prompt. Either way, the rating still commits on timeout whether or
  not a comment is typed; a typed comment is sent with it.
- This keeps the existing `FeedbackModal` copy/keys reusable but moves the
  rendering inline. The modal component can be retired for this flow or kept
  only as a fallback — implementer's call, as long as the default is inline.
- **Decision (was open):** record-and-offer-inline, *not* auto-open a modal.
  Rationale: a modal on every thumbs-down is friction; the rating is the signal
  and the comment is a bonus.

### 3. Explicit maintainer-sharing notice on thumbs-down

- The notice sits **right next to the thumbs-down comment field** (where the
  text is written), as a **short, plain** line — distinct from the generic
  "logged" notice. New i18n key (do not overload `privacyNotice`):
  - `Feedback.maintainerNotice`: *"Your message will be shared with the app's
    maintainer."* (kept short, as requested).
- It is **thumbs-down specific** (that is the flow that emails a person) and
  must appear in the UI even though the same fact is in the Terms of Use — the
  Terms are not a substitute for in-context disclosure.
- **Decision (was open):** show two short lines for thumbs-down — the
  maintainer notice first (it's the point), then keep the existing logging
  notice. Two clear facts beat one long merged sentence.

## Acceptance Criteria

- [ ] After tapping thumbs-up or thumbs-down, no feedback request is sent for
      ~10s; an inline countdown + **Undo** is shown.
- [ ] Undo (and re-tapping/switching the thumb) within the window cancels the
      pending feedback — verified that **no** network call to the feedback
      endpoint is made.
- [ ] After the window elapses, the rating commits (POST sent) with no forced
      modal; the buttons then lock against double-submission.
- [ ] The comment field is optional and inline (no pop-up modal blocks the
      conversation); a typed comment is sent with the rating.
- [ ] Exactly **one** feedback request per rating — at the ~10s mark when no
      comment, or on Send/blur when a comment is opened (countdown pauses while
      typing). Verified the maintainer email is not sent twice.
- [ ] Countdown is rendered as a quiet progress bar (not ticking seconds).
- [ ] Tapping thumbs-down shows a short, explicit notice — next to the comment
      field — that the message will be shared with the app's maintainer,
      separate from the generic logging notice.
- [ ] New i18n key(s) (e.g. `maintainerNotice`, plus any undo/countdown
      strings) added to **all** locale files under `frontend/messages/`
      (en, de, es, fr, hi, it, ko, pt, ru, zh, ar) — no missing-key warnings;
      `frontend/src/test/translations.test.ts` passes.
- [ ] Countdown is accessible (keyboard + screen reader) and honours
      `prefers-reduced-motion`.
- [ ] Window length is a single named constant, easy to change.
- [ ] Unit/component tests cover: pending state, undo cancels (no POST),
      timeout commits (POST sent), thumbs-down shows maintainer notice.
- [ ] No change to the backend contract is required for the web change; if the
      backend/Android are updated for parity it is tracked separately.

## Files Likely to Change

| File | Change |
|---|---|
| `frontend/src/components/ChatMessage.tsx` | Pending state, countdown + Undo affordance, defer `onFeedback` commit |
| `frontend/src/app/[locale]/ChatIsland.tsx` | Manage pending timer / cancellation around `handleFeedbackClick` / `handleFeedbackSubmit`; commit on timeout |
| `frontend/src/components/FeedbackModal.tsx` | Move comment + notices inline (retire modal for this flow, or keep as fallback); add maintainer notice for `rating === "negative"` |
| `frontend/messages/*.json` | New `Feedback.maintainerNotice` (+ any countdown/undo keys) in all 11 locales |
| `frontend/src/components/FeedbackModal.test.tsx`, `ChatMessage` tests, `translations.test.ts` | Cover new behaviour and keys |

## Decisions (resolved — great-UX direction)

- **Thumbs-down on timeout:** record the rating; offer the comment **inline and
  optional**. No auto-opened modal. ✔
- **Notice placement:** `maintainerNotice` sits next to the inline comment field
  (where text is written). ✔
- **Both notices vs merged:** two short lines for thumbs-down — maintainer
  notice first, then the logging notice. ✔
- **Positive feedback:** thumbs-up gets the same rethink window; comment is the
  same optional inline field (no maintainer notice, since positive feedback does
  not email a person). ✔

- **Countdown style:** quiet progress bar, not ticking seconds. ✔
- **Send timing / number of sends:** one send per rating — at the ~10s mark if
  no comment, or on explicit Send/blur if a comment was opened (countdown
  pauses while typing). See "When is the feedback actually sent?" above. ✔

### Still worth a quick product check before build

- Whether to fully delete `FeedbackModal` or keep it behind a flag as a
  fallback. Default: inline.

## Out of Scope

- Android / iOS parity for the rethink window and notice — track as a separate
  follow-up story if desired (`android/.../ChatMessageItem.kt`,
  `ChatScreen.kt`, `strings.xml`).
- Changing **where** maintainer emails are routed — handled by BITB-032.
- Backend changes to the feedback contract or email templates.
- Changing the Terms of Use / privacy-policy text (this story adds in-context
  disclosure; legal copy is a separate decision).

## Notes

- The maintainer-sharing notice is a **trust/transparency** requirement from
  the product owner: people must be told in-context, not only in the Terms.
- The rethink window is also a small abuse/accident guard — it costs nothing
  and prevents impulsive or mis-tapped ratings (and the associated maintainer
  emails) from being sent.

## Assignee

frontend
