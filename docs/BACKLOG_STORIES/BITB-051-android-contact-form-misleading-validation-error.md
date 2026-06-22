# BITB-051: Android Contact Form Shows "Message Too Long" When the Real Problem Is the (Required) Email

**Status:** 🚧 In Progress
**Priority:** P2
**Size:** S (< 4 hrs)
**Created:** 2026-06-15

## User Story

**As an** Android user submitting the contact / feedback form,
**I want** a clear, accurate error that names the email field when my submission is rejected for a
missing or invalid email,
**so that** I am not misled into thinking my message was too long and can actually fix the real
problem.

## Why

A user reported that sending feedback from the Android app produced the error *"Your message is a
little long (max 300 characters)"* — but the message was **not** long. The true cause was the
email field: the backend now **requires** a valid email on `POST /api/v1/feedback/contact`, and
when it is missing or malformed the server returns **HTTP 422**. The Android app blindly maps
**every** 422 to the message-length error, so the user sees a wrong, confusing message and the form
feels broken. On top of that, the email field is still labelled *"optional"*, which directly
contradicts the backend contract and nudges users into the failing path.

Misleading errors on a contact form are especially costly: a user who wanted to reach the team is
told their (fine) message is the problem and gives up, so a legitimate contact attempt is lost.

## Current Behaviour

- The form sends a blank email as `null`:
  `ContactFormBottomSheet.kt:278` — `onSubmit(..., emailInput.ifBlank { null })`.
- The request model treats email as optional:
  `ContactRequestDto.email: String? = null` (`data/remote/models/ContactDto.kt:21`).
- The backend requires it: `ContactRequest.email: EmailStr = Field(...)` (`api/feedback/models.py:56`),
  so a missing/invalid email → **HTTP 422**.
- `ChatViewModel.submitContact(...)` (`presentation/viewmodels/ChatViewModel.kt`, ~`983-1003`)
  routes the failure through `mapExceptionToMessage(e)`, whose **422 branch always** returns the
  message-length string:
  `ChatViewModel.kt:1158-1159` → `R.string.error_message_too_long` with
  `MAX_MESSAGE_LENGTH` (300). That branch was written for the chat path, where an over-long message
  is the only realistic 422 — but the contact form reuses it.
- The email label still says optional:
  `R.string.contact_email_label` = "Your email (optional, for reply)" (`res/values/strings.xml:254`),
  with the equivalent "optional" wording in every localized `values-*/strings.xml`
  (de, ar, fr, it, es, hi, ko, ru, pt, zh).

**Web service was checked and does NOT have this bug.** `submitContactForm`
(`frontend/src/lib/api.ts:849-851`) throws a generic `Error("API error: <status>")` on any non-OK
response; the "message too long" classification lives only in the chat `streamMessage` path
(`api.ts:541-557`), never in the contact form. On web a missing/invalid-email 422 therefore shows
the generic `Contact.errorSend` ("Failed to send message…"), not a 300-character message, and the
web email label was already updated to required phrasing. The 300-character misreport is
**Android-only**; the web side has only a milder, separate gap (its error is not email-specific) —
see the optional web follow-up below.

## Proposed Behaviour

### Android — stop misreporting the 422 (core fix)

- Give the contact-form submit path its own error mapping instead of reusing the chat-centric 422
  branch in `mapExceptionToMessage`. Recommended minimal approach: in `submitContact`'s `catch`,
  map a 422 to a new contact-specific string rather than `error_message_too_long`.
  - Optionally parse the 422 body (`detail[].loc` / `type`) to distinguish a missing vs. invalid
    email, but a single "please enter a valid email so we can reply" message is sufficient.
- Mark email **required** in the form UI: validate non-empty and basic format before submit (block
  the Send button or show an inline field error), and stop coercing blank → `null` at
  `ContactFormBottomSheet.kt:278`.
- Update `contact_email_label` to required phrasing (mirror the web: e.g. "Your email (for our
  reply)") in the default `res/values/strings.xml` **and every** `values-*/strings.xml` locale, so
  no "optional" wording remains for the email label.
- Optionally make `ContactRequestDto.email` non-nullable once the UI guarantees a value.
- Add new strings, e.g. `error_contact_email_required` / `error_contact_email_invalid`, in the
  default and all localized `strings.xml`.

### Web — optional, smaller follow-up (not the reported bug)

- Make the contact-form failure email-specific instead of the generic `errorSend`:
  `submitContactForm` (`frontend/src/lib/api.ts:849-851`) can parse a 422 `detail` for the `email`
  field and throw a typed error; `ContactForm.tsx` catch then shows a new email-specific i18n key
  (added to all 11 locales). Web does not exhibit the 300-character misreport, so this is a
  nice-to-have, not the core bug.

## Acceptance Criteria

- [ ] Android: submitting the contact form with a missing or invalid email shows an
      **email-specific** error — never the "max 300 characters" message.
- [ ] Android: the chat path's genuine message-length 422 still maps to `error_message_too_long`.
- [ ] Android: Send is blocked (or an inline error shown) when the email is empty or malformed; a
      valid email submits successfully.
- [ ] Android: `contact_email_label` updated to required phrasing in the default and **all**
      `values-*/strings.xml`; no remaining "optional" wording for the email label.
- [ ] Android: blank email is no longer coerced to `null` before submit.
- [ ] Web (only if the follow-up is included): a 422 email failure renders an email-specific
      message instead of the generic `errorSend`.

## Tests to Add

- **Android (`android/app/src/test/...`):**
  - `viewmodels/ChatViewModelTest.kt` — a contact-form 422 (email-validation failure) produces an
    email-specific error string, **not** `error_message_too_long`; and a chat message-length 422
    still maps to `error_message_too_long`. This directly pins the regression.
  - `viewmodels/FormValidationTest.kt` (or a `ContactFormBottomSheet` validation test) — empty or
    malformed email blocks submit / surfaces an inline error; a valid email passes.
  - `repositories/ContactRepositoryImplTest.kt` — the request carries the email (no blank → null
    coercion) once email is required.
- **Web (`frontend/src/...`), only if the web follow-up is included:**
  - `lib/api.test.ts` — extend with a `submitContactForm` case: a 422 email body throws the
    email-typed error (mirror the existing `MessageTooLongError` 422 test).
  - `components/ContactForm.test.tsx` — a 422 email failure renders the email-specific message,
    not the generic `errorSend`.
- **Backend:** the 422 contract is already covered by BITB-043's `api/tests/test_feedback.py`
  (missing/invalid contact email → 422) — reference only, no new work here.

## Files Likely to Change

| File | Change |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt` | Contact-form 422 → email-specific message, not `error_message_too_long` |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ContactFormBottomSheet.kt` | Required email validation; stop `ifBlank { null }` |
| `android/app/src/main/kotlin/org/voxquieta/app/data/remote/models/ContactDto.kt` | Optionally make `email` non-nullable |
| `android/app/src/main/res/values/strings.xml` + all `values-*/strings.xml` | Update `contact_email_label`; add `error_contact_email_required` / `_invalid` |
| `android/app/src/test/kotlin/.../viewmodels/ChatViewModelTest.kt` | New 422-mapping tests |
| `android/app/src/test/kotlin/.../viewmodels/FormValidationTest.kt` | Email-required validation test |
| `android/app/src/test/kotlin/.../repositories/ContactRepositoryImplTest.kt` | Email carried through request |
| `frontend/src/lib/api.ts`, `frontend/src/components/ContactForm.tsx`, `frontend/messages/*.json`, `frontend/src/lib/api.test.ts`, `frontend/src/components/ContactForm.test.tsx` | Optional web follow-up |

## Out of Scope

- BITB-043's broader feedback work (full feedback emails, reason chips).
- Backend changes — `ContactRequest.email: EmailStr` validation is already correct.
- The web "optional" label (already fixed) — only the optional email-specific error remains.

## Related

- `BITB-052` — Web follow-up: make the web contact form show an email-specific error on a 422
  instead of the generic "failed to send" (web has no 300-character misreport).
- `BITB-043` — Require Contact Email + Full Feedback Email Content + Negative-Feedback Reason
  Chips. BITB-043 made email required server-side but did not cover the Android client's misleading
  error message or the Android "optional" label; this story closes that gap.
