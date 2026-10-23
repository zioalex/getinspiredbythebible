# BITB-231: Right-Size the Server B2s → B1ms — Gated on halfvec's RAM Proof

**Status:** 🎯 Todo (blocked by BITB-230)
**Priority:** P2
**Size:** S (one Terraform change + observation) — the analysis is the work
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — Part B lever 2, deliberately last)

## User Story

**As** the owner paying 42.10 CHF/mo for a 2 vCore / 4 GB server whose CPU never
exceeds a fraction of one core, **I want** the SKU down-sized to B1ms *once the
evidence says the search working set survives it*, **so that** I cut ~17 CHF/mo
without re-inflicting the search latency this project has paid to fix before.

## The evidence so far (and the one number that says WAIT)

From the 90-day metrics and cost evidence:

| Metric | p50 | p95 | Gate | Status |
|--------|-----|-----|------|--------|
| CPU % | 6.6 | **8.1** | p95 < 30 → downsize ok | ✅ 10× headroom |
| Memory % | 46.8 | **58.1** | p95 < 60 → downsize ok | ⚠ 1.9 points from the gate |
| Storage % | 33.9 | 63.6 | < 70 (no imminent grow) | ✅ (but see BITB-229) |

Compute meter: **42.10 CHF/mo** on B2s; B1ms (1 vCore / 2 GB) runs ≈25 CHF/mo
class → **saving ≈17 CHF/mo**, the largest single SKU lever on the board.

**The 58.1% is the whole story.** The B2s was a deliberate upgrade from B1ms so
the per-translation partial HNSW set stays cached (BITB-150 quotes migration
007's rationale). At 4 GB, p95 58% means the working set *barely* fits today;
at 2 GB it categorically does not (~7.7 GB of vectors+indexes). Reversing the
B2s decision without first shrinking the working set would trade money for the
exact latency regression BITB-062 etc. were built to prevent.

## The gate: BITB-230 must prove RAM headroom first

After halfvec halves the vector+index footprint:

1. **B2s observation window (≥2 weeks):** memory p95 must drop well below 58%
   (expect ~35-45%) — recorded in this file with the same evidence-collection
   tooling
2. **Go/no-go:** B1ms only if post-halfvec memory p95 on B2s < 45% AND
   `chat_ttft`/`search latency p95` alerts stay green through the window
3. **Canary downgrade:** B1ms apply off-peak; watch `prod-monitor.yml` probes +
   the `scripture_search_latency_p95` alert for 48h; rollback = one config
   change (B-series restart, minutes)

## Reservation interaction (BITB-227)

If the B2s reservation is already purchased: PostgreSQL Flexible Server
reservations allow exchanges within the burstable family — the exchange path
(and its pro-rating) is confirmed in BITB-227's terms check. Sequence note:
216 explicitly recommended buying-now-and-exchanging over waiting; this story
is why that check mattered.

## Acceptance Criteria

- [ ] BITB-230 merged and its post-cutover memory numbers recorded here
- [ ] ≥2-week B2s window: memory p95 < 45%, CPU p95 < 30%, zero search-latency
      alert firings attributable to cache misses
- [ ] Go/no-go decision recorded with the numbers (a NO with evidence is a
      perfectly good outcome of this story — that's the point of the gate)
- [ ] If GO: SKU change in `deployment/main.tf` (B_Standard_B1ms), applied
      off-peak, 48h probe+alert observation window documented
- [ ] Post-change evidence pull: compute meter drops to the ~25 CHF class
- [ ] Reservation reconciled (exchange per BITB-227 terms, or expiry handled)

## Out of Scope

- General Purpose / D-series (no evidence path leads there; CPU is idle)
- Storage size (BITB-229)

## Related

- BITB-150 — parent; "down-sizing is the last lever considered, not the first"
- BITB-230 — hard prerequisite (the RAM proof)
- BITB-227 — reservation exchange mechanics
- BITB-062 — the latency class of regression this gate exists to prevent
