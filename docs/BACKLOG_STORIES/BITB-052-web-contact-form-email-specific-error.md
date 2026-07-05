# BITB-052: Web Contact Form Should Show an Email-Specific Error on a 422 (Not a Generic "Failed to Send")

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S (< 2 hrs)
**Created:** 2026-06-16

## User Story

**As a** web user submitting the contact form,
**I want** a clear error that names the email field when my submission is rejected for an invalid
email,
**so that** I can fix it directly instead of seeing a generic "failed to send" that gives no hint.

## Why

This is the web follow-up spun out of **BITB-051** (the Android contact-form bug). The web frontend
does **not** share Android's "your message is a little long (max 300 characters)" misreport — but it
has a milder, separate gap: when the contact submission is rejected for a missing/invalid email
(HTTP 422), the web shows a generic "Failed to send message…" with no indication that the email is
the problem. Email is already required on the web (label and disabled-submit), but a **non-empty but
malformed** email passes the client guard, reaches the API, and yields the generic error — an
actionable, email-specific message would close the loop.

## Current Behaviour

- `submitContactForm` throws a generic error on any non-OK response — it never parses the 422 body
  to identify the failing field: `frontend/src/lib/api.ts:849-851`
  (`throw new Error(\`API error: ${response.status}\`)`).
- `ContactForm.tsx` catches and shows the generic `t("errorSend")` regardless of cause:
  `frontend/src/components/ContactForm.tsx:76-78` →
  `Contact.errorSend` = "Failed to send message. Please try again or email us directly."
  (`frontend/messages/en.json:240`).
- The chat path already does this correctly and is the pattern to mirror: `streamMessage` inspects
  the 422 `detail[].type`/`loc` and throws a typed `MessageTooLongError`
  (`frontend/src/lib/api.ts:541-557`; class at `api.ts:72-75`).
- Email is already required client-side (label `Contact.emailLabel` = "Your email (for our reply)"
  in all 11 locales, `frontend/messages/*.json:220`; input `required` + submit disabled when empty),
  so the remaining hole is the malformed-but-non-empty email that round-trips to a 422.

## Proposed Behaviour

- In `submitContactForm`, on `response.status === 422`, parse the JSON `detail` and, when it points
  at the `email` field (inspect `loc`/`type`, mirroring `streamMessage`), throw a typed error such
  as `InvalidContactEmailError` (mirroring `MessageTooLongError`). Otherwise keep the existing
  generic throw.
- In `ContactForm.tsx`, catch the typed error and show a new email-specific i18n key
  (`Contact.errorEmailInvalid`) instead of `errorSend`; keep `errorSend` as the fallback for all
  other failures.
- Optional: add inline client-side format validation so a non-empty malformed email is blocked (or
  flagged on the field) before submit, avoiding the round-trip for the common case.
- Add `Contact.errorEmailInvalid` to all 11 `frontend/messages/*.json` locale files.

## Acceptance Criteria

- [ ] A 422 email-validation rejection renders an email-specific message, **not** `errorSend`.
- [ ] Other (non-422 / non-email) failures still show `errorSend`.
- [ ] `Contact.errorEmailInvalid` present in all 11 locale files.
- [ ] (Optional) A non-empty malformed email is caught client-side before submit.

## Tests to Add

- `frontend/src/lib/api.test.ts` — a `submitContactForm` 422 whose body identifies the `email`
  field throws the email-typed error (mirror the existing `MessageTooLongError` 422 test ~`1006`).
- `frontend/src/components/ContactForm.test.tsx` — a 422 email failure renders the email-specific
  message, not the generic `errorSend`.

## Files Likely to Change

| File | Change |
|---|---|
| `frontend/src/lib/api.ts` | Parse 422 `detail` in `submitContactForm`; new typed error |
| `frontend/src/components/ContactForm.tsx` | Catch typed error → email-specific message; optional inline format check |
| `frontend/messages/*.json` | Add `Contact.errorEmailInvalid` in all 11 locales |
| `frontend/src/lib/api.test.ts` | 422 email-error test for `submitContactForm` |
| `frontend/src/components/ContactForm.test.tsx` | Email-specific error rendering test |

## Out of Scope

- Android (tracked by **BITB-051**).
- Backend — `ContactRequest.email: EmailStr` validation is already correct.
- The "optional" email label — already fixed on web.

## Related

- `BITB-051` — Android contact/diagnostic email error; this is its web follow-up.
- `BITB-043` — made the contact email required server-side.
