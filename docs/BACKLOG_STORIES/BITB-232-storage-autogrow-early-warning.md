---
id: BITB-232
status: in-review
priority: P2
size: S
rank: 330
created: 2026-10-23
prs: [1340]
---

# BITB-232: Storage Auto-Grow Early Warning — the Alert That Catches the Ratchet

**Parent:** BITB-150 (Phase 0 follow-up — the ratchet finding turned into a guard)

## User Story

**As** the owner whose disk already doubled silently (32 → 64 GB) and whose
Terraform can no longer see the real size, **I want** an early-warning alert on
storage growth, **so that** the next auto-grow event pages me *before* the disk
ratchets to 128 GB and the bill takes another permanent step up.

## Why the existing alert cannot catch this

The current `db_storage` metric alert (`deployment/monitoring.tf`, threshold
**>85% over 30 min**) fires when the disk is nearly *full* — but auto-grow exists
precisely so the disk never stays full. The failure mode is the opposite of what
an 85% threshold detects:

- Today: 16 GB on a 64 GB disk = **25%**. Even post-backfill spikes stay < 70%.
- After a hypothetical 64 → 128 GB grow: utilization *drops* to ~12% and the
  85% alert becomes *further* from firing than ever.

**The 32 → 64 GB doubling happened with this alert green the whole time.** The
risk isn't "disk full", it's "disk doubled".

## The design (two signals)

1. **Pre-grow threshold:** a second metric alert on `storage_percent` at
   **70% sustained 15 min** (p95 is already 63.6% — this must be tuned against
   real variance so it warns, not pages). Fired → investigate what's writing
   before auto-grow makes it moot.
2. **Post-grow drift tripwire:** a scheduled check (Logic App or the weekly
   evidence workflow) comparing *provisioned* `storageSizeGb` against the
   Terraform-declared 32 GB — any mismatch means auto-grow fired; page Telegram.
   This is the only signal that catches the event itself, because utilization
   percentages go *down* when it happens. (This is also the guard the
   `prod-deploy-drift.yml` gap left open: it checks deployment drift, not
   server-size drift.)

## Acceptance Criteria

- [x] 70%/15-min `storage_percent` alert added in `deployment/monitoring.tf`
      (`db_storage_pregrow`, sev3), tuned so the current p95 (63.6%) does NOT
      page, and threshold + rationale documented in the resource description
- [x] Provisioned-size tripwire implemented (`db-storage-size` job in
      `prod-deploy-drift.yml` running `scripts/monitor/check_db_storage_size.py`)
      — compares `az postgres flexible-server list` `storageSizeGb` vs the
      expected size; mismatch pages Telegram (see Implementation notes for the
      64 GB baseline)
- [ ] Owner step: after deploy, test-fire the pre-grow alert once (temporarily
      lower its threshold, or use the Azure portal "test action group") and
      confirm delivery
- [ ] Owner step: run Actions -> Prod Deploy Drift with `force_alert=true` and
      confirm the `db-storage-size` Telegram message arrives (workflow_dispatch
      cannot override the workflow-level `EXPECTED_DB_STORAGE_GB`, so
      `force_alert` is the way to exercise the page path)
- [x] Alert wiring follows the existing action-group pattern (same channel as
      other DB alerts)
- [x] `deployment/README.md` notes the guard and the 64 GB expectation
      (declared 32 GB; BITB-229)

## Implementation notes

- **Re-page until acknowledged in code.** A grow is irreversible, so the tripwire
  re-pages about every 30 min until a PR updates `EXPECTED_DB_STORAGE_GB` — accepted
  as a forcing function (not a 3am action). BITB-229 now carries the matching update step.
- **Cadence:** the pre-grow alert evaluates every PT15M over a PT15M window (BITB-223:
  sev3 next-day signal, so not a PT5M rule).
- **Deviation: baseline is 64 GB, not the declared 32 GB.** The live disk
  already ratcheted 32 -> 64 GB and Terraform cannot shrink it, so comparing to
  32 would page forever. `EXPECTED_DB_STORAGE_GB: "64"` lives in
  `prod-deploy-drift.yml`; lower it to 32 when BITB-229 lands. `main.tf`'s
  `storage_mb = 32768` is only the provisioning size for a new server.
- The guard fails closed: zero servers, missing/non-numeric size, missing
  expected value or an `az` failure all page rather than look green.
- Tests: `api/tests/test_db_storage_size_guard.py`.

## Out of Scope

- Shrinking the disk (BITB-229)
- Any change to `auto_grow_enabled` (it stays true — the guard watches, it
  doesn't disarm the safety net)

## Related

- BITB-150 — parent; ratchet finding, `ignore_changes` context
- BITB-229 — the actual size fix this guard watches over
- BITB-223 — frequency conventions for the new rules follow its matrix
