---
id: BITB-329
status: in-review
priority: P1
size: L
created: 2026-11-16
prs: [1311]
---

# BITB-329: Bound, Minimise and Disclose Stored Feedback Text and Contact-Form Data

**Prompted by:** the independent verification of BITB-326 (PR #1303, 2026-11-16). This gap
predates #1303 and was checked against the code. Spec confirmed by the owner on 2026-11-16.

## Problem

The published privacy policy (`frontend/public/legal/privacy-policy*.md`, 11 languages)
contradicts what the backend stores and sends.

1. **Feedback** (`Feedback`, table `feedback`) stores the following, with **no expiry**:
   - `user_message`, `assistant_response` and the free-text `comment`;
   - the **raw** `session_id`.

   The policy calls this "thumbs-up/thumbs-down ratings" and says chat messages are not
   retained.
2. **Contact form** (`ContactSubmission`, table `contact_submissions`) stores an optional
   `email`, the message, `session_id` and `user_agent`, with no expiry. The policy says "We do
   not collect your … email address".
3. **Notification emails** (`api/utils/email_service.py`, sent through **SMTP2GO**, which the
   policy never mentions):
   - feedback emails carry the user's message, the AI reply and the comment;
   - contact emails carry the message and set `Reply-To` to the sender's address.

   These copies sit in the owner's mailbox, beyond any limit the code can enforce.
4. BITB-326's GDPR sentence says blocked-message records are "not linked to you". They carry
   a session-id hash, so "not linked to your identity" is more exact.

## Owner decisions (2026-11-16)

- Feedback text (`user_message`, `assistant_response`, `comment`): kept **30 days**.
- The rest of a feedback row (rating, reason, message id, verses, model, timing, session hash):
  **90 days**.
- Contact submissions: **90 days**.
- Session id: stored as a **one-way hash**. Contact `user_agent`: **no longer stored**.
- Notification emails carry **identifiers only**: no message text, AI reply, comment or
  reply-email address. The full text is read with a new `make export-feedback` while it exists.
  **Each email must be easy to act on:**
  - the exact `make` commands to run, with that item's id filled in;
  - the firewall step;
  - the date its text will be deleted;
  - the how-to doc link.
- Same rules for contact messages (no `Reply-To`; the address is read via the export).

## Functional requirements

1. **Retention, enforced in code.** Extend the hourly in-app sweep (`api/main.py`
   `_purge_ttl_samples`, which also runs at startup) with:
   - feedback rows older than `FEEDBACK_TEXT_RETENTION_DAYS` (30): set `user_message`,
     `assistant_response` and `comment` to NULL;
   - feedback rows older than `FEEDBACK_RETENTION_DAYS` (90): delete;
   - contact submissions older than `CONTACT_RETENTION_DAYS` (90): delete.

   Ages are counted from `created_at`. No code path may update `created_at`. Settings live in
   `api/config.py` and `scripts/env-manifest.yaml` (`required_in: none`). Validate
   1 ≤ text ≤ row ≤ 3650.
2. **Minimisation.**
   - `FeedbackRepository.save_feedback` / `save_contact` store
     `sha256(session_id).hexdigest()`, the same function as `feedback/blocked_samples.py`
     `_hash_session_id`. Reuse it rather than copying it.
   - `save_contact` stops writing `user_agent`. The request field may stay accepted and ignored,
     for old clients.
   - **Alembic revision `r0010`** (data-only, no DDL):
     - hash existing raw session ids, i.e. rows whose `session_id` is not already 64 hex chars
       (`encode(sha256(convert_to(session_id,'UTF8')),'hex')`), in both tables;
     - set `contact_submissions.user_agent = NULL`.

     The docstring states the lock level and duration and sets `lock_timeout` /
     `statement_timeout`. Downgrade is a documented no-op, since hashing is irreversible.
     Follow `docs/MIGRATION_GUIDELINES.md`.
3. **Export tool.** New `scripts/export_feedback.py` plus `make export-feedback ARGS=…`,
   following `scripts/export_blocked_samples.py`. It is read-only, takes `DATABASE_URL`, and
   writes JSON or CSV.
   - Feedback selectors: `--message-id <uuid>`, `--id <n>`, `--since`, `--until`,
     `--rating`, `--limit`.
   - `--contacts` with `--id <n>`, `--since`, `--subject`, `--limit`.

   It never returns rows past their limits: feedback text is already NULL after 30 days; the
   query also filters `created_at > now() - interval`. Document it in
   `docs/HOW-TO-EXPORT-FEEDBACK.md`, including prerequisites (az login, `make az-pg-add-ip`,
   `make db-server-url`, `make az-pg-remove-ip`), and link it from the blocked-samples how-to.
4. **Actionable notification emails** (`send_feedback_notification` /
   `send_contact_notification`; text and HTML bodies):
   - **Remove** `user_message`, `assistant_response`, `comment` and the contact message/email
     from the bodies, and drop `reply_to`.
   - **Keep**: rating and reason, message id (feedback) or row id and subject (contact), model,
     response time, verse references, whether a comment or reply address exists (yes/no),
     timestamp.
   - **Add** a "How to read the full text" block with **copy-pasteable commands for this exact
     item**, e.g.:

     ```bash
     make az-pg-add-ip
     export DATABASE_URL="$(make -s db-server-url SERVER=<prod server>)"
     make export-feedback ARGS="--message-id <uuid>"
     make az-pg-remove-ip RULE=<rule>
     ```

     Contacts use `ARGS="--contacts --id <n>"`.
   - Also add: "Text available until <created_at + 30 days, ISO date>" (contacts: + 90 days),
     and a link to `docs/HOW-TO-EXPORT-FEEDBACK.md` on GitHub.
   - Commands must be exactly what works. Check every target and flag name against the
     Makefile and the scripts. Read the prod server name from settings or config. If it isn't
     available in the API, print `<server>` with a one-line hint to run `make db-server-url`
     without SERVER, or check `deployment/terraform.tfvars`.
5. **Privacy policy, all 11 languages:**
   - Feedback bullet: the message, AI reply and comment are kept 30 days; rating, reason and
     message id 90 days; session id only as a one-way hash; purpose: improving answers.
   - Contact form: subject, message and the optional reply email are kept 90 days, only to
     answer you.
   - "Data We Do NOT Collect": keep the sentence but carve out an email you choose to give in
     the contact form.
   - Third-party table: add **SMTP2GO**: notification emails to the operator, which contain no
     message content (link to its privacy policy).
   - Data Retention: add bullets for feedback and contact with the numbers.
   - GDPR section:
     - feedback and contact data **can** be found and deleted on request (give the message
       id, or the email used);
     - blocked-message records are "not linked to your identity" (BITB-326 wording fix).
   - `lastUpdated` bump.
6. **No retention extension.** No code path refreshes `created_at`, and the sweep never touches
   younger rows.

## Non-functional requirements

- Privacy: logs never contain message, reply, comment or email text.
- The sweep is idempotent, bounded in batch size, and never raises: it follows the
  `_purge_ttl_samples` pattern.
- 11 languages for the policy text. The UI string `privacyNotice` already says text is logged.
  Update it in all 11 web locales and the Android strings to mention "kept 30 days", if they
  exist on Android.

## Acceptance criteria

- [x] Retention sweep tests: text cleared at 30 days and not before; feedback rows deleted at 90
      days; contacts deleted at 90 days; younger rows untouched; settings respected; validation
      bounds.
- [x] Hashing tests for new writes (same digest as blocked samples) and for migration `r0010`
      (already-hashed values untouched; user_agent cleared). `alembic` up/down on a test DB if
      CI's Alembic job covers it.
- [x] Email tests: bodies (text + HTML) contain none of: the user message, the AI reply, the
      comment, the contact message or the reply email. They contain the exact export commands
      with the id, and the deletion date. No `reply_to`.
- [x] Export tool tests (query filters, no expired rows, CLI flags) under `api/tests/`, so CI
      runs them.
- [x] `legal-pages.test.tsx`: feedback, contact and SMTP2GO disclosures plus the retention numbers
      in all 11 languages. A backend test ties the policy numbers to the settings. Both fail on
      the current policy.
- [x] `make test-makefile` audit (`scripts/make_target_audit.json`, `docs/MAKE_TARGET_AUDIT.md`)
      updated for `export-feedback`.
- [ ] Owner step: **before the first deploy**, export anything worth keeping. The first sweep
      clears feedback text older than 30 days and deletes feedback older than 90 days and
      contacts older than 90 days.
- [ ] Owner step: review the policy text in the 10 translations before merge.

## Out of scope

- Admin UI. A pg_cron backstop: the in-app sweep runs hourly and at startup, and the export
  filters by age.
- The data inventory and CI guard (BITB-328) will include these stores.
