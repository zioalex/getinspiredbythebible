# BITB-229: Shrink the PG Disk 64 → 32 GB via Dump/Restore

**Status:** 🎯 Todo (blocked by BITB-228)
**Priority:** P2
**Size:** M (planned maintenance window + runbook)
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — the storage-ratchet answer)

## User Story

**As** the owner of a server whose disk auto-grew 32 → 64 GB while the database
never exceeded 16 GB, **I want** the provisioned storage brought back to 32 GB,
**so that** the storage meter stops climbing (3.17 → 4.67 → 6.55 CHF/mo,
Jul→Sep), the backup bill halves, and the next auto-grow ratchet step
(64 → 128 GB, ~+4.7 CHF/mo) is pushed years away instead of months.

## The evidence

- `05a`: provisioned **64 GB** (Terraform still declares 32 GB — `main.tf:415-421`
  with `lifecycle.ignore_changes = [storage_mb]`; the declared value has been
  fiction since the auto-grow)
- `05b`: actual database **16 GB**
- `05c`: of that, ~6.8 GB is dead indexes — **BITB-228 must land first**, or the
  restore target needslessly carries dead weight
- Meter: storage line rising month over month; a further auto-grow doubles it again
- Storage utilization p95 **63.6%** of 64 GB (`06-storage_percent.json`) — i.e.
  ~10 GB headroom; another backfill or a halfvec transition rebuild could trip it

## Why a dump/restore (and not a shrink)

Azure Flexible Server storage **cannot be reduced in place** — the disk grows
only. The only supported path to a smaller provisioned size is a new server:

1. Off-peak: `pg_dump` the current database (16 GB — minutes, not hours;
   the runbook basis exists in `scripts/db-backup-restore.sh`)
2. Create the replacement server at 32 GB (B2s, same region/version/extensions)
3. Restore; verify row counts + `alembic_version` + the 17 evidence-file
   equivalents of a health check (or a targeted subset)
4. Repoint `DATABASE_URL` (Terraform var / Key Vault secret); recycle the backend
5. Delete the old server — **this is the step that actually saves money**;
   skipping it means paying for two servers

Terraform implication: the new server means a **new resource id**. The clean way
is `terraform state mv`-style import or a planned replacement — the repo's
Terraform must end up managing the new server with `storage_mb = 32768`
still true (and `ignore_changes` retained, per BITB-150's ratchet note).

## Honest savings math

- Direct: 64 GB → 32 GB ≈ **2.4 CHF/mo** (meter-derived 0.075 CHF/GB/mo)
- Backup storage billed against provisioned size: roughly halves (≈ additional
  ~1-2 CHF/mo class, verify from the backup meter line post-change)
- Ratchet avoidance: next doubling (64→128) would add ~4.7 CHF/mo — pushed from
  "a bad backfill away" to "several years away" at 16-17 GB on 32 GB
- **Total realistic: ~4-7 CHF/mo + a truthful Terraform state.** This story
  exists because it also *un-blocks* honest capacity planning; it is not the
  big line on the bill and shouldn't be sold as one.

## Acceptance Criteria

- [ ] BITB-228 confirmed merged (dead indexes gone) before scheduling
- [ ] Runbook executed in staging (or a scratch server) end-to-end once first
- [ ] Maintenance window: low-traffic UTC hours; `prod-monitor.yml` expectations
      documented (brief health-probe failures during cutover are expected and
      must not page falsely — coordinate with BITB-223's suppression work)
- [ ] New server: 32 GB, same SKU/region, verified `alembic_version` match,
      row-count spot-checks on `verses`/`translations`
- [ ] Old server deleted only after 48h of green probes on the new one
- [ ] Terraform state reconciled: the managed server is the new one; no
      duplicate-cost drift
- [ ] Post-change evidence re-collected (the `05a` equivalent shows 32 GB;
      storage meter line drops in the next Cost Management pull)

## Out of Scope

- Compute SKU (BITB-231) — but note the same maintenance window could combine
  both if sequencing allows; decide at planning time
- `halfvec` (BITB-230) — do NOT combine with a table-rewrite migration in one
  window; separate blast radii

## Related

- BITB-228 — blocker (shrink target must exclude dead indexes)
- BITB-230/220 — sibling sequencings; one window, one change
- BITB-150 — parent; the ratchet finding and `ignore_changes` context
- `scripts/db-backup-restore.sh` — existing backup/restore runbook to build on
