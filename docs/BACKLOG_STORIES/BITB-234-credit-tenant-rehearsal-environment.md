# BITB-234: Second-Tenant Rehearsal Environment — Spend the $50 Credit on Migrations, Not on Splitting Production

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (Terraform for a minimal rehearsal stack + teardown discipline + cost guard)
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — new-tenant opportunity, evidence-based scope)

## User Story

**As** the owner of a second, empty Azure tenant holding a one-time **$50 credit**
(tenant `e306deba-ab4e-48d3-8619-f57acb138a6a`), **I want** it used as a
**rehearsal and burst-workload environment** for the upcoming database migrations,
**so that** the riskiest operations (halfvec backfill, index rebuilds, disk
shrink, B1ms canary) are proven against real Azure infrastructure before they
touch production — and the credit buys capability instead of a permanent
cross-tenant dependency that outlives it.

## Why this scope — the honest options analysis

The $50 is **one-time** (≈half a month of current spend at 92.73 CHF/mo).
Four candidate uses, evaluated:

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| **A. Rehearsal/staging environment** (recommended) | **DO** | The migration chain (BITB-230 halfvec, BITB-229 disk shrink, BITB-231 B1ms canary) is exactly the class of change `docs/MIGRATION_GUIDELINES.md` (and the 2026-08-17 outage retro) requires rehearsing. The repo has wanted this before (branches `claude/rehearse-connection-error`, `claude/alembic-rehearse-in-azure`) but had no cheap place to put it. A credit-funded rehearsal stack is ephemeral by design: when the rehearsals are done, tear it down and keep whatever credit remains. |
| **B. Permanently split production across tenants** | **DECLINE** | Moving any prod component (e.g. frontend Container Apps, 4.61 CHF/mo) buys ~3 months of offset, then costs the same again — plus cross-tenant complexity forever: public-endpoint auth instead of private networking, two Terraform states, two CI/CD targets, two sets of credentials, egress traffic, and a funding story ($80/mo Ko-fi goal) that counts real spend in *both* tenants once credits expire. Savings ≈ one-time $50; costs ≈ permanent operational surface. |
| **C. Buy the reserved capacity there** (BITB-227 substitute) | **DECLINE** | Azure reservations apply only to subscriptions in the same billing tenant/enrollment — a reservation purchased in the credit tenant does **not** discount the production tenant's B2s. (And reservations are not purchasable in the current billing setup at all, which is why BITB-227 was cancelled.) |
| **D. Home the new PG server for BITB-229's shrink** | **DECLINE** | A production database in a different tenant from its app adds latency, egress cost, and an expiry cliff under the credits. The shrink story keeps its new server in the production tenant. |

Burst workloads that also fit option A: golden-set live runs (BITB-230's recall
gate), embedding backfill rehearsals, and dry-runs of the dump/restore runbook
(`scripts/db-backup-restore.sh`) before BITB-229 touches prod.

## What the rehearsal environment is

Minimal, deliberately disposable:

- **PostgreSQL Flexible Server** (B1ms, 32 GB, same region/version/extension set
  as prod — `pgvector`) — restored from a prod `pg_dump` so rehearsals run
  against realistic data volumes (16 GB)
- **Log Analytics workspace** (PerGB2018) — only if a rehearsal needs its alerts
  wired; otherwise skip
- **No public app front-end** — rehearsals are operator-run (psql, migration
  scripts, golden-set runner); no Container Apps unless a specific rehearsal
  needs the app (then: the existing images from the primary ACR or a temporary
  instance)
- Terraform: reuse the existing `deployment/` modules where possible with a
  separate root/state (new backend config keyed to the second tenant), driven
  by a dedicated least-privilege SPN created by the same pattern as
  `scripts/create_cost_collection_spn.sh`

## The cost discipline (the $50 must not silently evaporate)

Evidence-derived: a B1ms runs ~21 CHF/mo if left on. **Flexible Servers support
stop/start — a stopped server bills only storage (~0.10 CHF/mo class).** So:

- Budget alert on the credit subscription at **80% of remaining credit**
- The rehearsal server is **stopped between sessions** (`az postgres
  flexible-server stop`) — start only for a rehearsal window, stop after
- A teardown checklist story-step: after BITB-230 and BITB-229 rehearsals pass,
  `terraform destroy` the stack and record the remaining credit
- Monthly one-line check (fold into the weekly evidence workflow) of the credit
  tenant's spend so a leak pages the owner

## Acceptance Criteria

- [ ] Options analysis above confirmed/adjusted with the owner (especially: prod
      stays whole in the primary tenant — this story must not become a split)
- [ ] Second-tenant SPN created (least-privilege: Contributor scoped to a new
      `bible-app-rehearsal-rg` only) and its credentials stored wherever the
      rehearsal CI/ops run from — never in the prod repo's secrets
- [ ] Terraform: rehearsal root + state for the second tenant, reusing prod
      module patterns; `terraform plan` reviewed; resources: B1ms PG server
      (stopped after apply), rehearsal resource group
- [ ] One rehearsal proven end-to-end: a prod `pg_dump` restored into the
      rehearsal server, and the BITB-230 halfvec phase-1/2 (column add + one
      backfill batch) executed there — timings recorded into BITB-230's story
      file as the planning input
- [ ] Stop/start discipline demonstrated: server stopped at the end of the
      rehearsal window; billing shows storage-only cost while stopped
- [ ] Budget alert at 80% of the credit configured on the credit subscription
- [ ] Teardown: documented command sequence (`terraform destroy` + SPN cleanup)
      ready as a checklist in this story; executed when the migration chain
      ships — remaining credit recorded here
- [ ] `deployment/README.md` gains a short "Rehearsal environment (second
      tenant)" section pointing to this story

## Out of Scope

- Moving any production component to the credit tenant (declined above)
- A permanent staging environment with CI deployments (this is a rehearsal
  sandbox; if the project later wants permanent staging, that's its own story
  with its own funding decision)
- Cross-tenant networking (peering/private endpoints) — not needed for
  operator-run rehearsals over public endpoint + firewall

## Related

- BITB-230 (halfvec), BITB-229 (disk shrink), BITB-231 (B1ms) — the consumers
- BITB-227 — cancelled the same day; the compute saving now rides on BITB-231
- BITB-150 — parent analysis; the cost evidence that sizes the rehearsal stack
- `docs/MIGRATION_GUIDELINES.md`,
  `docs/RETROSPECTIVES/2026-08-17-tsvector-migration-outage.md` — why rehearsals
- `scripts/db-backup-restore.sh` — the dump/restore tooling rehearsed here
