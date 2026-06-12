# BITB-043: Require Contact Email + Full Feedback Email Content + Negative-Feedback Reason Chips

**Status:** 🚧 In Progress
**Priority:** P2
**Size:** M (1-2 days)
**Created:** 2026-06-08

## User Story

**As a** user submitting a contact form or leaving feedback,
**I want** to be prompted for my email address (so the team can actually reply),
and when I leave negative feedback I want to quickly label what went wrong with a single tap,
**so that** the team can follow up with me and act on precise, categorised feedback rather
than guessing what the problem was.

## Why

1. **Contact form without email = dead end.** The current contact form makes email optional.
   In practice most users do not fill it in, leaving the team with a message they cannot
   follow up on. Making email required closes that loop.

2. **Feedback emails were truncated and content-poor.** The maintainer email sent on negative
   feedback silently cut the user message and AI response at 500 characters (losing context),
   lacked structured metadata (model, response time, verses cited, message ID), and had no HTML
   formatting. A bare positive rating with a comment also went silently into the DB but sent
   no email — the team never saw it.

3. **Negative feedback has no category.** A thumbs-down means "something was wrong" but not
   *what* was wrong. Five quick-tap reason chips (Inaccurate / Unhelpful / Wrong verse / Tone /
   Other) let the user express the failure type in one tap, giving the team actionable signal
   without asking them to write an essay.

## Current Behaviour

- `ContactRequest.email` is optional (`str | None`); the frontend sends it only if filled in.
- The submit button is not blocked when email is empty.
- `send_feedback_notification` only fires on `rating == "negative"`, truncates both message
  fields at 500 characters, has no HTML, and no metadata table.
- `FeedbackRequest` and the `Feedback` SQLAlchemy model have no `reason` field (the plan
  already added it, but the UI and email path do not use it).
- No "What went wrong?" chips in `FeedbackControls.tsx`.

## Proposed Behaviour

### Contact form — email required

- Backend: `ContactRequest.email: EmailStr = Field(...)` — required, validated.
- Frontend: `required` attribute on the `<input type="email">`, guard in `handleSubmit`,
  disabled send button when email is empty, body sends `email: email.trim()` (not `|| undefined`).
- i18n: `Contact.emailLabel` updated to "Your email (for our reply)" in all 11 locales.

### Feedback email — full content + context + HTML + positive-with-comment

- Route: also notifies maintainer when `rating == "positive"` AND comment is non-empty.
- Route: passes all fields (message_id, verses_cited, model_used, response_time_ms, reason)
  to `send_feedback_notification`.
- Email service: removes the `if rating != "negative": return True` early-exit guard.
- Email service: removes all truncation — full user message and AI response rendered.
- Email service: adds HTML body with sectioned layout (Comment, Reason chip, Original
  Question, AI Response, metadata table).

### "What went wrong?" reason chips — negative panel only

- `FeedbackControls.tsx` adds a `reason` state (string | null) and renders five quick-tap
  chips (Inaccurate, Unhelpful, Wrong verse, Tone, Other) when `pending === "negative"`.
- Selecting a chip is optional — auto-commit still proceeds without it.
- `onSubmit` prop widened: `(rating, comment, reason?) => void`.
- Wiring through `ChatMessage.tsx` → `ChatIsland.tsx` → `FeedbackRequest.reason`.
- New migration `scripts/migrations/006_add_feedback_reason.py` adds
  `ALTER TABLE feedback ADD COLUMN IF NOT EXISTS reason VARCHAR(40)`.

## Acceptance Criteria

- [ ] POST `/api/v1/feedback/contact` without email → HTTP 422
- [ ] POST `/api/v1/feedback/contact` with invalid email → HTTP 422
- [ ] POST `/api/v1/feedback/contact` with valid email → HTTP 200/500 (depending on DB)
- [ ] Frontend contact form: send button disabled when email is empty; `required` on input
- [ ] `Contact.emailLabel` updated in all 11 locale files to required phrasing
- [ ] Negative feedback email sent with full (untruncated) user message and AI response
- [ ] Positive feedback WITH a comment triggers a maintainer email
- [ ] Positive feedback WITHOUT a comment sends no email (unchanged)
- [ ] Maintainer email includes HTML body with metadata table (model, response time, verses, ID)
- [ ] Thumbs-down panel shows 5 reason chips; selecting one then Send passes it to `onSubmit`
- [ ] Chip selection is optional — auto-commit still works without it
- [ ] `reason` persisted to DB via `Feedback.reason` column
- [ ] Migration 006 adds `reason VARCHAR(40)` column safely (`IF NOT EXISTS`)
- [ ] All 11 locale files have `reasonPrompt`, `reasonInaccurate`, `reasonUnhelpful`,
      `reasonWrongVerse`, `reasonTone`, `reasonOther`
- [ ] Backend tests pass: `test_submit_contact_missing_email` and
      `test_submit_contact_invalid_email` assert 422
- [ ] Frontend tests: reason chips coverage in `FeedbackControls.test.tsx`

## Files Likely to Change

| File | Change |
|---|---|
| `api/feedback/models.py` | `ContactRequest.email` required; `FeedbackRequest.reason` + SQLAlchemy column (already in plan) |
| `api/requirements.txt` | `email-validator` (already present) |
| `api/pyproject.toml` | `email-validator` dependency (already present) |
| `api/routes/feedback.py` | Broaden email trigger; pass all fields |
| `api/utils/email_service.py` | Full content, HTML, no truncation, new params |
| `api/feedback/repository.py` | `reason=request.reason` on `Feedback(...)` |
| `api/tests/test_feedback.py` | Add email to fixtures; new 422 tests; update email call assertions |
| `scripts/migrations/006_add_feedback_reason.py` | New migration |
| `frontend/src/components/ContactForm.tsx` | `required`, guard, body change |
| `frontend/src/components/FeedbackControls.tsx` | `reason` state, chips, widened `onSubmit` |
| `frontend/src/components/ChatMessage.tsx` | Widened `onSubmitFeedback` type |
| `frontend/src/app/[locale]/ChatIsland.tsx` | `reason` param wiring |
| `frontend/src/lib/api.ts` | `reason?: string` on `FeedbackRequest` |
| `frontend/messages/*.json` | `emailLabel` + 6 reason keys in all 11 locales |
| `frontend/src/components/FeedbackControls.test.tsx` | New chip coverage tests |
| `docs/BACKLOG.md` | Summary entry |
| `docs/BACKLOG_STORIES/BITB-043-*.md` | This file |

## Out of Scope

- Android parity for reason chips — track separately if desired.
- Changing `contact_submissions.email` DB column (stays nullable for historical rows).
- Making the reason chips available on thumbs-up feedback.
- Changing the email routing destination (handled by BITB-032).
