# BITB-233: PostgreSQL Server-Log Hygiene — Dead Parameters and the Unmade Diagnostic Decision

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — resolves the Part A/Part B overlap finding)

## User Story

**As** the owner of a server generating server-side logs that nothing reads and
no one decided to keep, **I want** the log-producing server parameters either
turned off or deliberately wired to a sink, **so that** the configuration
reflects an actual decision instead of an accident — and a future "turn on PG
diagnostics" never silently doubles my monitoring bill.

## The finding (the story's "highest information-per-minute check", resolved)

BITB-150 flagged the tension: `main.tf` sets three log-producing parameters, but
**no `azurerm_monitor_diagnostic_setting` for the PostgreSQL server exists in
Terraform**. Phase 0 evidence settles it:

- `04-postgres-diagnostic-settings.json` = **`[]`** — confirmed: **no diagnostic
  setting exists**, in Terraform *or* as portal drift.
- Therefore `log_connections = on` (main.tf:531-536), `log_checkpoints = on`
  (:517-522) and `log_min_duration_statement = 100` (:510-515) write logs that
  exist only on the server's local disk. Cost impact today: **zero ingestion**
  (nothing reaches Log Analytics). Operational value today: near zero (nobody
  reads server-local logs; they rotate away).

## The decision this story records (pick one, deliberately)

**Option A — Turn the noise off (recommended):**

- `log_connections = off` — on a pooled-connection app this log line fires per
  connection establishment; pure noise at this traffic level.
- `log_checkpoints = off` — valuable on a write-heavy server tuning checkpoints;
  this workload is read-dominated.
- `log_min_duration_statement = 100` — **keep** (or raise to ~200): it is the
  one parameter with a plausible future reader (slow-query diagnosis), cheap,
  and local-only until a sink exists.

**Option B — Wire a sink deliberately:** add a Terraform
`azurerm_monitor_diagnostic_setting` (PGSQLLogs → the workspace) *with* a
workspace retention/cost estimate, keep all three parameters, and accept the
ingestion. Only worth it if the owner actually wants query logs — Phase 0 says
nothing today reads them, so the default recommendation is A.

**Why this matters beyond pennies:** the trap is a future "quick fix" that adds
the diagnostic setting by hand in the portal while the parameters stay maxed —
instant Terraform-invisible ingestion (the exact drift class BITB-150 warned
about; `prod-deploy-drift.yml` doesn't watch diagnostic settings). This story
makes the state *and the intent* explicit.

## Acceptance Criteria

- [ ] Decision (A or B) recorded here with reasoning
- [ ] If A: `log_connections = off`, `log_checkpoints = off` in Terraform
      (`azurerm_postgresql_flexible_server_configuration` blocks),
      `log_min_duration_statement` kept with a comment on why
- [ ] If B: diagnostic setting codified in Terraform with the estimated
      ingestion cost written down *before* enabling
- [ ] Either way: a one-line note in `deployment/README.md` stating the
      decision, so the "should we log PG queries?" question has an answer on
      record
- [ ] Server restart/connection-drain impact verified off-peak (parameter
      changes recycle the server in some cases — confirm per parameter class
      and schedule)

## Out of Scope

- Log Analytics cap (BITB-225), alert rules (BITB-223)
- Any change to query logging *format* or `pg_stat_statements`

## Related

- BITB-150 — parent; the overlap table that framed this question
- BITB-056 — where the parameters originally came from
- BITB-225 — the cap that bounds the sink if Option B is ever chosen
