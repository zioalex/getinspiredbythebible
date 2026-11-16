---
id: BITB-329
status: todo
priority: P1
size: M
created: 2026-11-16
---

# BITB-329: Disclose (or Bound) Stored Feedback Text and Contact-Form Email in the Privacy Policy

**Prompted by:** the independent verification of BITB-326 (PR #1303, 2026-11-16). This is a
gap that predates #1303 and was checked against the code. Filed in the same PR per *Backlog
Hygiene*.

## Problem

The published privacy policy (`frontend/public/legal/privacy-policy*.md`, 11 languages)
contradicts what the backend stores:

1. **Feedback.** The `Feedback` model (`api/feedback/models.py`, table of thumbs-up/down
   submissions) stores the following, with **no expiry and no purge**:
   - `user_message` (the user's chat message);
   - `assistant_response` (the AI reply);
   - the free-text `comment`;
   - the **raw** `session_id`.

   The policy says:
   - "Feedback ratings: Optional thumbs-up/thumbs-down ratings you submit on responses";
   - "Chat messages: Not retained on our servers" (after BITB-326: "…except messages blocked
     by our safety system").

   The UI itself warns that "your message and the AI response will be logged"
   (`frontend/messages/*.json` `privacyNotice`), so the product already behaves this way. The
   policy just doesn't say so.
2. **Contact form.** `ContactSubmission` stores an optional `email`, the message, the
   `session_id` and the `user_agent`, while the policy's "Data We Do NOT Collect" says "We do
   not collect your name, email address, or phone number". There is no retention period.
3. **Wording precision (minor).** BITB-326's GDPR paragraph says blocked-message records are
   "not linked to you". They carry an unsalted SHA-256 of the session id (pseudonymous), so
   "not linked to your identity" is more exact.

## Requirements

- Decide per store (owner decision, see Open questions): **disclose** the current behaviour,
  or **bound** it with a TTL + purge like blocked samples, or **minimise** it (hash the session
  id, drop `user_agent`).
- Update all 11 policy translations: what is stored, why, how long, and how to request deletion
  (feedback and contact rows *can* be found by message id / email, unlike blocked samples).
- Implement any TTL / minimisation in code with tests (a repeat or update never extends
  retention).
- Extend `frontend/src/test/legal-pages.test.tsx`:
  - assert the feedback and contact disclosures exist in all 11 languages;
  - assert the old blanket claims are gone ("collect no personally identifiable information",
    "do not collect your … email" without the contact-form exception).
- Fold both stores into the BITB-328 data inventory.

## Open questions

- Retention for feedback text and contact submissions: keep indefinitely (disclosed), or e.g.
  90 days / 12 months?
- Should feedback keep `user_message` / `assistant_response` at all, or only `message_id`,
  rating and reason?

## Acceptance criteria

- [ ] Policy (11 languages) matches what feedback and contact store, and for how long.
- [ ] Any chosen TTL / minimisation implemented and tested.
- [ ] Tests fail on the current policy and pass after.
- [ ] Owner step: decide the retention periods and review the translated policy text before merge.
