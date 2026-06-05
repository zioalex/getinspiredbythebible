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

## Proposed Behaviour

### 1. "Rethink" / undo window (~10s) — both ratings

When the user taps thumbs-up or thumbs-down:

- Reflect the choice immediately in the UI (the tapped thumb fills/highlights)
  but treat it as **pending, not committed**.
- Show an inline, non-blocking affordance with a countdown and an **Undo**,
  e.g. *"Sending in 10s… Undo"*, counting down.
- If the user taps **Undo** (or re-taps the same thumb, or switches to the
  other thumb) within the window, cancel the pending action — no request is
  sent and the buttons return to their neutral, re-tappable state.
- When the countdown elapses, commit:
  - **Thumbs-down** → open the feedback modal (so they can add a comment) OR,
    if we want zero-friction, record the rating and offer the comment modal as
    an optional follow-up. **Decision needed** (see Open Questions).
  - **Thumbs-up** → record the positive rating (current product sends a
    positive rating with optional comment via the modal; keep parity unless we
    decide thumbs-up should be one-tap with an optional "add a note" link).
- The window length must be a single named constant (e.g.
  `FEEDBACK_RETHINK_MS = 10_000`) so it is easy to tune.
- Respect `prefers-reduced-motion` for the countdown animation; the countdown
  must be screen-reader friendly (announce "Undo available" rather than
  spamming each tick).

### 2. Explicit maintainer-sharing notice on thumbs-down

- At the point of thumbs-down (in the rethink affordance and/or the feedback
  modal), show a **short, plain** line stating the comment will be shared with
  the app's maintainer — distinct from the generic "logged" notice.
  Suggested copy (new i18n key, do not overload `privacyNotice`):
  - `Feedback.maintainerNotice`: *"Your message will be shared with the app's
    maintainer."* (kept short, as requested).
- This notice is **thumbs-down specific** (that is the flow that emails a
  person). It must appear in the UI even though the same fact is in the Terms
  of Use — the Terms are not a substitute for in-context disclosure.
- Keep the existing `privacyNotice` (logging) as-is or fold it in; do not
  remove the logging disclosure. **Decision needed** on whether to show both
  lines or merge them for thumbs-down.

## Acceptance Criteria

- [ ] After tapping thumbs-up or thumbs-down, no feedback request is sent for
      ~10s; an inline countdown + **Undo** is shown.
- [ ] Undo (and re-tapping/switching the thumb) within the window cancels the
      pending feedback — verified that **no** network call to the feedback
      endpoint is made.
- [ ] After the window elapses, the rating commits and the thumbs-down comment
      flow opens as today; the buttons then lock against double-submission.
- [ ] Tapping thumbs-down shows a short, explicit notice that the message will
      be shared with the app's maintainer, separate from the generic logging
      notice.
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
| `frontend/src/app/[locale]/ChatIsland.tsx` | Manage pending timer / cancellation around `handleFeedbackClick` / `handleFeedbackSubmit` |
| `frontend/src/components/FeedbackModal.tsx` | Add explicit maintainer-sharing notice for `rating === "negative"` |
| `frontend/messages/*.json` | New `Feedback.maintainerNotice` (+ any countdown/undo keys) in all 11 locales |
| `frontend/src/components/FeedbackModal.test.tsx`, `ChatMessage` tests, `translations.test.ts` | Cover new behaviour and keys |

## Open Questions / Decisions Needed

- **Thumbs-down on timeout:** open the comment modal automatically (today's
  behaviour, shifted by 10s), or record the rating immediately and make the
  comment optional? Recommend: keep opening the modal so the maintainer notice
  is seen and comments are encouraged.
- **Notice placement:** show `maintainerNotice` in the inline rethink
  affordance, the modal, or both? Recommend: the modal (where the comment is
  written) at minimum; optionally a hint in the inline affordance.
- **Both notices vs merged:** for thumbs-down, show logging + maintainer lines
  separately, or one combined sentence? Recommend: two short lines to keep each
  fact clear.
- **Positive feedback:** does thumbs-up also get the rethink window (yes, per
  request — applies to both), and does it still open the comment modal? Keep
  current modal behaviour unless product wants one-tap positive.

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
