---
id: BITB-233
status: in-review
priority: P2
size: S
rank: 340
created: 2026-10-23
---

# BITB-233: PostgreSQL Server-Log Hygiene — Dead Parameters and the Unmade Diagnostic Decision

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
- Therefore `log_connections = on` (`log_connections` resource in `deployment/main.tf`), `log_checkpoints = on`
  (`log_checkpoints` resource) and `log_min_duration_statement = 100` (`log_min_duration_statement` resource) write logs that
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

## Decision (2026-11-26)

**Option A.** Phase-0 evidence shows no diagnostic setting exists, so the logs go
only to server-local disk and nothing reads them.

- `log_connections` is noise on a pooled app: now `off`.
- `log_checkpoints` matters little on a read-dominated workload: now `off`.
- `log_min_duration_statement` stays at 100 ms: the one parameter a future reader
  will plausibly want (slow-query diagnosis); costs nothing until a sink exists.
- Both `off` resources are kept in Terraform so state is managed explicitly
  (deleting a configuration resource resets the parameter to the Azure default, which is `on`).
- **Restart impact:** `log_checkpoints` has context `sighup` and `log_connections`
  has context `superuser-backend` (applies to new connections). Neither is a
  static parameter, so Azure Flexible Server applies both without a restart.
- `scripts/migrations/003_tune_postgresql_config.sql` is reference-only (SQL is
  commented out); only a BITB-233 comment was added there.
- Guard test: `api/tests/test_pg_server_log_params.py`.

## Acceptance Criteria

- [x] Decision (A or B) recorded here with reasoning
- [x] If A: `log_connections = off`, `log_checkpoints = off` in Terraform
      (`azurerm_postgresql_flexible_server_configuration` blocks),
      `log_min_duration_statement` kept with a comment on why
- [ ] N/A (Option A chosen) — If B: diagnostic setting codified in Terraform with the estimated
      ingestion cost written down *before* enabling
- [x] Either way: a one-line note in `deployment/README.md` stating the
      decision, so the "should we log PG queries?" question has an answer on
      record
- [ ] Owner step: no restart is expected because both parameters are non-static.
      After the deploy, confirm with
      `az postgres flexible-server parameter show --name log_connections ...`
      (and `log_checkpoints`); `isConfigPendingRestart` should be false

## Out of Scope

- Log Analytics cap (BITB-225), alert rules (BITB-223)
- Any change to query logging *format* or `pg_stat_statements`

## Related

- BITB-150 — parent; the overlap table that framed this question
- BITB-056 — where the parameters originally came from
- BITB-225 — the cap that bounds the sink if Option B is ever chosen
