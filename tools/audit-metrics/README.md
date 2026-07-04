# audit-metrics

Trend tracking for the adversarial risk audits (`docs/audits/`): are the
findings, the monolith files, and the hygiene debt going up or down over
time? Companion to `tools/repo-metrics/` — same conventions (stdlib-only
Python, dated JSON snapshots, rendered report + self-contained dashboard).

## Outputs (committed under `docs/audits/metrics/`)

| File | What |
|---|---|
| `report.md` | Trend tables: risk score, findings by severity/category, hotspot LOC, hygiene counters, test surface |
| `index.html` | Self-contained dashboard with trend lines (open locally) |
| `history/YYYY-MM-DD.json` | Dated snapshot — accumulates so runs can be compared over time |

## Run it

```sh
make audit-metrics
```

or directly:

```sh
python3 tools/audit-metrics/analyze.py   # audits + worktree → history/<today>.json
python3 tools/audit-metrics/render.py    # snapshots → report.md + index.html
```

Run it after every `/risk-audit` (the audit playbook says so), and let
`.github/workflows/audit-metrics.yml` take a monthly snapshot in between so
hotspot/hygiene drift is visible even when no audit ran.

## What the numbers mean

- **Risk score** — weighted open findings of the latest audit report:
  CRITICAL=10, HIGH=5, MEDIUM=2, LOW=1. The absolute value is arbitrary;
  the direction between snapshots is the signal.
- **Open finding** — a `### <ID> —` block in the newest
  `docs/audits/YYYY-MM-adversarial-audit.md` whose `[STATUS]` is not
  RESOLVED (the baseline report has no STATUS lines; everything counts as
  open). Category comes from the ID prefix (A/E/S/D/O).
- **Hotspot watch** — line counts of the files the audits flagged as
  monoliths or hand-synchronized copies (`HOTSPOTS` in `analyze.py`; keep
  in sync with the parity ledger in `docs/AUDIT_PLAYBOOK.md`). Shrinking is
  the goal; `null`/— means the file was deleted, which is a win.
- **Hygiene counters** — grep-cheap proxies for audit findings: sync
  `httpx.Client(` in `api/` (S1), `runBlocking` on Android (S6), suppressed
  lint, TODO/FIXME/HACK in code (docs excluded), tracked cruft files,
  docker-compose variants.
- **Test surface** — test-file counts per area plus Playwright e2e specs;
  the one table where up is good.

Lower is better for everything except the test surface. Tune the hotspot
list, hygiene patterns, and severity weights at the top of `analyze.py`.
