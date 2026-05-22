# BITB-032: Route Support/Diagnostic Emails to `support@voxquieta.org`

## User Story

As the product team, I want contact-form submissions and diagnostic bug
reports from the Android app (and any other client of the backend's
feedback endpoint) to land in `support@voxquieta.org` instead of
`contact@voxquieta.org`, so support requests are handled by the right
inbox and not mixed with general inbound mail.

## Problem

Both the Android "Send Diagnostic Report" flow
(`DiagnosticReportBottomSheet`) and the "Get in Touch" contact form
(`ContactFormBottomSheet`) POST through the backend endpoint
`/api/v1/feedback/contact` (`android/.../BibleApiService.kt:71`). The
backend's email service then relays a notification to a single configured
recipient.

That recipient is `contact@voxquieta.org` today (`api/config.py:92`,
default value of `contact_notification_email`). The product intent is to
have a dedicated `support@voxquieta.org` inbox for actionable issues so
they aren't lost in a general contact mailbox.

## Background — How the email recipient is wired

- **Setting**: `api/config.py:92`

  ```python
  contact_notification_email: str = "contact@voxquieta.org"
  ```

- **Usage**: `api/utils/email_service.py:142` and `:215` —

  ```python
  to_email = settings.contact_notification_email
  ```

  Used for both contact-form submissions and negative-feedback (thumbs
  down) notifications.
- **Env override**: documented in `deployment/README.md:863` —
  `CONTACT_NOTIFICATION_EMAIL=your-email@example.com`. Production almost
  certainly sets this via environment variable, so the deployed value
  must be updated; flipping only the default in `config.py` is not
  sufficient on its own.

## Proposed Changes (Option 1 — recommended)

Change the single setting that drives both flows.

1. **Update the default** in `api/config.py`:

   ```python
   contact_notification_email: str = "support@voxquieta.org"
   ```

2. **Update the deployed environment value** of
   `CONTACT_NOTIFICATION_EMAIL` to `support@voxquieta.org` in whichever
   deployment system holds it (e.g. Container Apps env config / Terraform
   under `infra/`, or a GitHub Actions secret). The implementer must
   identify the actual source — search the repo for
   `CONTACT_NOTIFICATION_EMAIL` and update every place it's set.
3. **Refresh the doc examples** in `deployment/README.md` (lines 845,
   863, 870, 871) so the example email matches the new convention.
4. **Verify mail server**: confirm `support@voxquieta.org` exists as a
   real mailbox or alias before flipping the default. Coordinate with
   whoever runs the mail provider. Until that's verified, treat this
   story as blocked.

## Why not introduce a separate setting?

Considered: add a new `support_notification_email` and route only
diagnostic reports there, keeping the contact form on
`contact@voxquieta.org`. **Not recommended** for now:

- Doubles config surface and requires plumbing a second recipient
  through `email_service`.
- The two flows already share a single backend endpoint and template;
  splitting them is a bigger change than the user story justifies.
- A shared `support@` inbox can route internally with mail rules if
  triage requires.

Revisit only if support volume makes a single inbox unworkable.

## Acceptance Criteria

- [ ] `api/config.py` default for `contact_notification_email` is
      `support@voxquieta.org`.
- [ ] Production `CONTACT_NOTIFICATION_EMAIL` is set to
      `support@voxquieta.org` in every deployment config file (list each
      file in the PR description).
- [ ] `deployment/README.md` examples reference the new address.
- [ ] `pytest api/tests/test_email_service.py` passes. Existing tests
      stub `mock_settings.contact_notification_email = "admin@example.com"`
      (lines 264, 301, 339, 371, 399, 437) and do not assert the literal
      `contact@voxquieta.org`, so no test should need editing — confirm
      this by running the suite.
- [ ] Manual QA after deploy: submit a diagnostic report from the
      Android app on a build pointing at the updated environment; verify
      the notification arrives at `support@voxquieta.org`.
- [ ] Manual QA: submit a contact-form message; verify it also lands at
      `support@voxquieta.org`.

## Files to Modify

| File | Change |
|---|---|
| `api/config.py` | Change default of `contact_notification_email` to `support@voxquieta.org` |
| `deployment/README.md` | Update example values around lines 845, 863, 870, 871 |
| `infra/**` and any GH Actions / Container Apps env config | Update `CONTACT_NOTIFICATION_EMAIL` (paths TBD by implementer) |

## Out of Scope

- Changing the SMTP **sender** address (`noreply@voxquieta.org`) — sender
  identity stays the same.
- Changing `frontend/messages/*.json:124` (`errorConnection`) — those are
  user-facing fallback contact addresses ("if the problem persists, you
  can reach us at `contact@voxquieta.org`) and a separate decision.
  Flagged here so we don't accidentally couple them.
- iOS app (no current iOS support email flow).
- A separate `support_notification_email` setting (see "Why not"
  section).
- Mail provider provisioning of the new mailbox — that's a prerequisite
  tracked outside this story.

## Priority

P1 — High once the mailbox is provisioned. Small change but directly
affects how support requests are received in production.

## Size

XS — under 1 hour of code change. Most of the work is locating every
deployment config that sets `CONTACT_NOTIFICATION_EMAIL`.

## Dependencies / Prerequisites

- `support@voxquieta.org` must exist (or be aliased) on the mail
  provider before merging.

## Assignee

backend / devops
