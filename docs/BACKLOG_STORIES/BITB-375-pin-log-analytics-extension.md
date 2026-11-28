---
id: BITB-375
status: todo
priority: P2
kind: chore
size: XS
created: 2026-11-28
depends_on: [BITB-374]
---

# BITB-375: Install the log-analytics az extension where `az monitor log-analytics query` runs

## Problem

The BITB-374 linter found that `az monitor log-analytics query` is not a core Azure CLI command: it
lives in the `log-analytics` extension (with azure-cli 2.93.0 and dynamic install off the CLI answers
"'query' is misspelled or not recognized"). Two callers use it without ever installing the extension:

- `.github/workflows/prod-monitor.yml` (the "Query for backend errors" step, line ~402), run on
  a schedule against production;
- `scripts/az-logs.sh:67` (`make az-logs-*-query`), run on a developer laptop.

`scripts/collect_cost_evidence.py` already documents the same gotcha ("the collector never calls
`az monitor log-analytics query`, because that command needs the log-analytics extension"). Whether
the monitor job works today depends on the runner image's default for extension dynamic install, which
is not under the repo's control.

## Requirements

- `prod-monitor.yml`: add a step before the query that runs
  `az extension add --name log-analytics --version <pin> --yes`, using the version pinned in
  `scripts/az-extensions.txt` (single source of truth, e.g. read it with `grep`/`cut`).
- `scripts/az-logs.sh`: fail early with a message naming `az extension add --name log-analytics`
  when the query command is unavailable, instead of the CLI's "misspelled" error.
- Confirm in the first scheduled run that the query step succeeds.

## Acceptance criteria

- [ ] `prod-monitor.yml` installs the pinned extension before the query step; `az-lint` stays green.
- [ ] `az-logs.sh` prints an actionable message when the extension is missing.
- [ ] Owner step: none expected; if the scheduled `prod-monitor` run fails on the install, report it here.
