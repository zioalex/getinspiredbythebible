# BITB-043: Product Analytics Dashboard (Metabase)

**Priority:** P2 — Medium. Follows the weekly digest email (which ships the
same metrics now); this is the longer-term, interactive successor.
**Status:** 📋 Proposed — not yet started.
**Size:** L (multi-day: infra + DB role + dashboard authoring).
**Created:** 2026-06-08

---

## Context

The owner wants a **proper dashboard** for product/business signals — positive
vs. negative feedback, contact submissions, web-vs-mobile engagement, languages,
DAU/MAU — across both the web app and the Android app. The weekly digest email
(`api/reports/weekly_report.py` + `.github/workflows/weekly-report.yml`) is the
deliberate **stopgap**: it surfaces these numbers now, by email, with zero new
infra. This story is the planned evolution into an interactive dashboard, and
it's designed so the email work is a stepping stone rather than a throwaway.

## What already exists (and why it isn't this)

There IS a dashboard in the repo:
`deployment/azure-monitor/workbook-performance-dashboard.json` — an Azure
Monitor Workbook (stories BITB-021 / BITB-022, deployed via Terraform
`azurerm_application_insights_workbook.performance_dashboard` in
`deployment/main.tf:1055`). But it is an **SRE / operational** view over
Application Insights using KQL: request volume, latency percentiles, TTFT, LLM
duration, errors, container CPU/memory.

It does **not** cover the **product/business** signals this request is about,
and it **cannot** easily: those signals live in the backend **Postgres** tables
(`feedback`, `contact_submissions`, `sessions`), not in Application Insights,
and the workbook is KQL-only against App Insights. So this is a *new, separate,
product-analytics* dashboard — not an extension of the SRE workbook.

## User Story

**As** the product owner,
**I want** an interactive dashboard of feedback, contact, and engagement metrics
sourced from the production Postgres DB,
**so that** I can explore trends (not just receive a weekly snapshot) without
writing SQL or logging into the database.

## Recommended solution: Metabase (self-hosted)

Evaluated Metabase vs. Grafana vs. Looker Studio vs. extending the Azure
Workbook. **Metabase** is the best fit because it uniquely covers all three
needs at once:

- **Business analytics, not just ops.** Built for non-technical users to build
  dashboards on a SQL DB without writing SQL — the right tool for product KPIs.
- **Connects straight to the existing Postgres DB** (`feedback`,
  `contact_submissions`, `sessions`) — the *same* data the weekly digest already
  queries. No new data pipeline needed for phase 1.
- **Built-in scheduled email "dashboard subscriptions"** — Metabase can email a
  dashboard digest on a weekly cadence out of the box. This is what lets the
  custom email endpoint be retired/relegated once the dashboard exists.
- **Self-hostable via Docker** — consistent with the existing Azure Container
  Apps + Postgres stack and Terraform-managed infra; data stays in-house.

### Self-host sketch (Azure Container Apps)

- Run the official `metabase/metabase` container as a new Container App
  (Terraform, alongside the backend).
- Metabase needs its **own small app-metadata database** (a dedicated Postgres
  DB / schema for Metabase's internal state — do **not** point it at the app
  tables for this).
- Give Metabase a **read-only Postgres role** scoped to the analytics tables
  (`feedback`, `contact_submissions`, `sessions`) for the data connection —
  never the app's read/write credentials.
- Put it behind authentication (Metabase has its own user management; optional
  SSO) and restrict ingress.
- Store the DB credentials as Container App secrets, same pattern as the backend.

### Dashboard content (phase 1)

Rebuild the digest's metrics as Metabase questions/dashboard cards:
feedback total + positive ratio + recent negative comments, contact submissions
by subject, active/new sessions, web-vs-mobile split, top languages, plus
week-over-week and longer trend lines that the email can't show.

### Email migration

Once the dashboard exists, switch the weekly Sunday email from the custom
endpoint to a **Metabase dashboard subscription**. Keep
`api/routes/admin.py` + the `weekly-report.yml` workflow as a lightweight,
no-dashboard fallback, or retire them — decide at migration time.

### Phase 2 — unify Android/Firebase engagement

Bring GA4 / Firebase Analytics (Android screen views, verse taps, retention)
into the picture — either export **GA4 → BigQuery** and add BigQuery as a
second Metabase data source, or stand up a **Looker Studio** board native to
GA4 and link it alongside. This is also where the Firebase work deferred from
the weekly-email story lands.

## Alternatives considered

- **Grafana** — excellent for ops/time-series and can read Postgres, but it is
  observability-oriented, not built for business reporting, and weak on
  scheduled business-KPI emails. Keep it for SRE, not this.
- **Looker Studio (free, Google)** — native GA4/Firebase connector; best
  reserved for the Android-engagement piece (phase 2). Can read Postgres via a
  connector but is less ergonomic for self-hosted SQL than Metabase.
- **Extend the Azure Monitor Workbook** — wrong data source (App Insights, not
  Postgres) and KQL-only authoring; not suited to feedback/business analytics.

## Acceptance Criteria

- [ ] Metabase runs as a Terraform-managed Azure Container App with its own
      metadata DB.
- [ ] A **read-only** Postgres role scoped to `feedback`, `contact_submissions`,
      `sessions` is created and used for the Metabase data connection.
- [ ] Metabase is behind authentication; ingress is restricted.
- [ ] A dashboard reproduces the weekly digest metrics (feedback, contact,
      engagement) plus trend views.
- [ ] A weekly Metabase email subscription is configured to
      `weekly_report_recipient`; the custom `weekly-report.yml` cron is then
      disabled or documented as fallback.
- [ ] Setup documented in `deployment/README.md`.

## Out of Scope

- Phase-2 GA4/Firebase/BigQuery integration (tracked as a follow-up).
- Replacing or modifying the SRE Azure Monitor workbook.
- Embedding the dashboard in the public web app (internal/admin use only).

## Dependencies / Prerequisites

- Weekly digest story (the metric SQL in `api/reports/weekly_report.py` is the
  reference for the dashboard cards).
- Read-only DB role provisioning on the production Postgres server.

## Assignee

devops / backend
