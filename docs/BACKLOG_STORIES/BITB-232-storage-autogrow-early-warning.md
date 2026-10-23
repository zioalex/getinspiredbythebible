# BITB-232: Storage Auto-Grow Early Warning — the Alert That Catches the Ratchet

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-23
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

- [ ] 70%/15-min `storage_percent` alert added in `deployment/monitoring.tf`,
      tuned so the current p95 (63.6%) does NOT page, and threshold + rationale
      documented in the resource description
- [ ] Provisioned-size tripwire implemented (weekly workflow step or Logic App)
      — compares `az postgres flexible-server show` storage vs the declared
      `storage_mb`; mismatch pages Telegram
- [ ] Both tested once: forced test-fire each (temporary threshold / simulated
      mismatch) and observed in Telegram
- [ ] Alert wiring follows the existing action-group pattern (same channel as
      other DB alerts)
- [ ] `deployment/README.md` notes the guard and the 32 GB expectation

## Out of Scope

- Shrinking the disk (BITB-229)
- Any change to `auto_grow_enabled` (it stays true — the guard watches, it
  doesn't disarm the safety net)

## Related

- BITB-150 — parent; ratchet finding, `ignore_changes` context
- BITB-229 — the actual size fix this guard watches over
- BITB-223 — frequency conventions for the new rules follow its matrix
