# BITB-227: Purchase 1-Year Reserved Capacity for the B2s Compute

**Status:** ❌ Cancelled (2026-10-23) — reserved capacity is **not purchasable in the
current billing setup** (owner-confirmed: no EA/MCA/CSP billing relationship that
supports Flexible Server reservations). The ~13.90 CHF/mo lever is void; the
compute-cost work shifts to **BITB-231** (B2s→B1ms right-size, ~17 CHF/mo), which
now carries the biggest single compute saving with no reservation-exchange
considerations. Nothing in this story is actionable as filed.
**Priority:** P2
**Size:** S (verify + document; the buy is a portal/CLI action)
**Created:** 2026-10-23
**Cancelled:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — Part B lever 1, ranked #1 by saving ÷ risk)

## User Story

**As** the owner paying on-demand rates around the clock for an always-on B2s,
**I want** a 1-year reserved-capacity purchase on its compute, **so that** I save
~13.90 CHF/month with zero engineering risk, no downtime, and no code change —
the single best saving-per-risk on the whole backlog.

## The numbers (from the meters, not list prices)

- DB compute (`Microsoft.DBforPostgreSQL/flexibleServers`, "Compute" meter):
  **42.10 CHF/mo** average Jul–Sep (`01-cost-by-resource-meter.json`) — the #1
  cost meter of the entire subscription
- Server: `Standard_B2s`, North Europe, provisioned 24/7 (`05a`)
- 1-year reserved-capacity discount on Flexible Server compute: **~33%**
  → expected **~13.90 CHF/mo saving** (≈167 CHF/year)
- CPU utilization p95 is **8.1%** (`06-cpu_percent.json`) — the server is not
  ephemeral and not seasonal; a full-year commitment matches reality

## The one real risk: the SKU might change within 12 months

The commitment trade BITB-150 flagged. Evidence-based view of what could move:

- **Right-sizing (BITB-231)** could take B2s → B1ms *after* the halfvec migration
  frees RAM. PostgreSQL Flexible Server reservations are per compute SKU, with
  exchange rules (same series/tier). **Sequencing options:**
  - (a) Buy B2s now, exchange toward B1ms if the downgrade happens — exchanges
    are allowed, pro-rated; some friction.
  - (b) Decide halfvec + right-size first (both are stories away), then buy the
    reservation for the *final* SKU — avoids any exchange but delays ~13.9 CHF/mo
    of savings for months.
  - **Recommendation: (a)** — at ~14 CHF/mo the saving outruns the exchange
    friction immediately, and the B1ms move is not yet evidence-cleared
    (memory p95 58.1% is near the 60% gate).
- **Tier upgrade (General Purpose)** is *not* plausible: CPU p95 8.1% (upgrade
  gate was p50 > 40% sustained). Nothing on the roadmap points there.

## Acceptance Criteria

- [ ] Size-flexibility/exchange terms for PostgreSQL Flexible Server reserved
      capacity confirmed at purchase time (document the exact terms here — the
      B2s→B1ms exchange path is the one that matters)
- [ ] 1-year reservation purchased for `Standard_B2s` in North Europe; scope
      aligned to the server's resource group/subscription
- [ ] Before/after evidence: the same Cost Management query from
      `cost-evidence-20261023-121757/01-cost-by-resource-meter.json` re-run
      post-purchase shows the flexibleServers compute meter drop ≈13-14 CHF/mo
- [ ] `deployment/README.md` cost table updated to reflect reserved pricing
- [ ] An expiry reminder exists (calendar/recurring task) ~1 month before
      renewal — the classic reservation trap is silently paying on-demand again

## Out of Scope

- Changing the SKU itself (BITB-231, gated on BITB-230)
- Storage/backup reservations (no such product for Flexible Server storage)

## Related

- BITB-150 — parent analysis; lever ranked #1
- BITB-230 (halfvec), BITB-231 (right-size) — the only SKU-moving scenarios;
  this story must stay compatible with both
