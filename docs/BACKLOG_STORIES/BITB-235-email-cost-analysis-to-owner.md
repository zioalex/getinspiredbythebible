# BITB-235: Email the Cost Analysis to the Owner — Private Delivery Instead of Public-Repo Evidence

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (report generator + workflow change + email wiring)
**Created:** 2026-10-24
**Parent:** BITB-150 (Phase 0 follow-up — resolves the deferred privacy decision)

## User Story

**As** the owner of a public repository whose weekly cost-evidence workflow
currently commits raw Azure billing data to a visible branch, **I want** the
cost analysis delivered to my email inbox ([EMAIL]) instead, **so that**
sensitive financial and operational details (exact spend per meter, alert
firing history, infrastructure capacity, index names and scan counts) never
land in a public repo — and the analysis arrives in a form I can read without
opening 18 JSON files.

## Why this exists — the privacy decision, resolved

BITB-150's analysis identified that the evidence files contain:

- **Financial**: exact Azure spend per meter (reveals infrastructure budget)
- **Security recon**: full alert-rule inventory + firing history (a map of
  what is and isn't monitored)
- **Infrastructure recon**: SKU, storage, capacity headroom, DB schema hints
  (index names, scan counts)
- **Identifiers**: workspace customer IDs, subscription IDs, resource names

None of this belongs in a public git history. The weekly workflow
(`cost-evidence-weekly.yml`) currently commits raw `cost-evidence-<ts>/`
directories to the repo — this story replaces that with private email
delivery, using infrastructure that already exists.

## The existing email infrastructure (no new services required)

| Component | Status | Where |
|-----------|--------|-------|
| SMTP2Go account | ✅ Active | `smtp2go_enabled = true`, `api/config.py:159-162` |
| Backend email service | ✅ Built | `api/utils/email_service.py` — already sends contact-form + weekly-report emails |
| Weekly report precedent | ✅ Proven | `.github/workflows/weekly-report.yml` (Sundays 18:00, backend `/api/v1/admin/weekly-report`, `dry_run` mode) |
| SMTP2Go API key | ✅ In secrets | Already wired for contact notifications (`SMTP2GO_API_KEY`) |
| Recipient | ✅ | `[EMAIL]` — same as `contact_notification_email` and the weekly report recipient |

The cleanest implementation follows the weekly-report pattern: the **backend**
does the work (it already has DB + SMTP), the workflow just triggers it.

## Design

### 1. Report generator (new `scripts/cost_report.py` or backend module)

Takes the collected evidence directory and produces a **human-readable
markdown/text report** — not a JSON dump:

```text
Vox Quieta Cost Analysis — Week of 2026-10-28

Billed (last 3 full months):  281.44 CHF (avg 93.81/mo)
  vs monthly_budget:          100 CHF  → within budget

Breakdown (monthly avg):
  Database (PostgreSQL)       46.90 CHF/mo  (50.6%)
  Monitoring                  25.26 CHF/mo  (27.2%)
  Other (Apps+ACR+OpenAI)     20.57 CHF/mo  (22.2%)

Top 5 meters:
  1. PG compute B2s                42.10 CHF/mo
  2. Scheduled query rules (20)   20.04 CHF/mo
  3. Container Apps backend        8.93 CHF/mo
  ...

Trends (vs last week):
  Storage meter: 4.80 → 4.85 CHF/mo  (ratchet watch)
  Alert firings: 143 → 127 (BITB-223 in effect)
  ...

Notable changes:
  ⚠  Provisioned storage changed: 64 → 65 GB (auto-grow fired — BITB-232 tripwire)
```

### 2. Weekly workflow change (`cost-evidence-weekly.yml`)

Replace the `git add cost-evidence-*` + commit + artifact-upload steps with:

1. Collect (unchanged)
2. Generate the report (`scripts/cost_report.py` reads the evidence dir)
3. Send via email — **SMTP direct from the workflow** using the existing
   `SMTP2GO_API_KEY` secret (simplest path; no backend endpoint needed for
   data that lives in the workflow, not the DB)
4. Upload the raw evidence as a **workflow artifact with short retention**
   (1 day) — accessible only to repo collaborators, not committed to git
5. **Delete the raw evidence from the runner** (already ephemeral — this is
   just explicit)

Alternative considered: backend endpoint (`/api/v1/admin/cost-report`, the
weekly-report pattern). Rejected for this story because the evidence lives in
the workflow's filesystem, not the production DB — piping 18 JSON files
through the API adds a request path for no gain. If the report later needs
DB-resident data (e.g. session counts), the backend route becomes worth it.

### 3. What stays in the repo

**Nothing.** No sanitized summary, no cost tables, no trend lines — the repo
gets no financial data at all. The public artifacts are the tooling
(collector, report generator) and the stories; the **output** is private
email. This is the strictest version of the privacy decision; if a sanitized
public trend page is ever wanted, that's a separate story with its own
redaction review.

## Acceptance Criteria

- [ ] `scripts/cost_report.py` — reads a `cost-evidence-*/` directory,
      produces a markdown report: 3-month totals, resource-type breakdown,
      top-5 meters, week-over-week deltas (reads the previous report from
      a workflow artifact or recomputes), auto-grow/storage-ratchet
      tripwire (BITB-232 signal), alert-firing summary
- [ ] Report generator has unit tests (parses the
      `cost-evidence-20261023-121757` fixture — the real evidence archive
      structure — without network access)
- [ ] `cost-evidence-weekly.yml` updated: email step via SMTP2Go
      (`SMTP2GO_API_KEY` secret, recipient `[EMAIL]`), 1-day artifact
      retention, **no git commit step** — the raw-evidence commit code
      is removed entirely
- [ ] One manual `workflow_dispatch` run produces the email in the inbox;
      `dry_run` input (matching weekly-report's pattern) prints the report
      to the workflow log without sending
- [ ] The evidence directory never appears in `git status` on any branch
      after the run
- [ ] `scripts/README_COST_COLLECTION.md` updated: "Output goes to email,
      not the repo" replaces the commit-based flow
- [ ] Old evidence directories already committed (if any landed during
      testing) purged from the branch history

## Out of Scope

- A public-facing cost/trend page (separate story if ever wanted)
- Telegram delivery (the existing Telegram channel stays for outage alerts;
      cost analysis is a weekly read, email is the right shape)
- Changing the collector itself (it already works and is CI-gated)

## Related

- BITB-150 — parent; the privacy concern was raised during its analysis
- BITB-232 — storage auto-grow tripwire; its signal feeds this report
- BITB-223 — alert rationalization; the report shows its effect on firing
  counts and the scheduled-query meter
- `weekly-report.yml` — the precedent for scheduled email delivery
- `api/utils/email_service.py` — the backend SMTP path (not used here, but
  the reference implementation)
