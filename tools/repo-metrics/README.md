# repo-metrics

Repo productivity retrospective: how much got built, how much got rebuilt,
and what it cost in quality — extracted entirely from git history and
`CHANGELOG.md`. Stdlib-only Python, no dependencies.

## Outputs (committed under `docs/metrics/`)

| File | What |
|---|---|
| `index.html` | Self-contained interactive dashboard (open locally or via GitHub Pages) |
| `report.md` | Written report with the same numbers as tables |
| `history/YYYY-MM-DD.json` | Dated snapshot — accumulates so runs can be compared over time |

## Run it

```sh
make repo-metrics
```

or directly:

```sh
python3 tools/repo-metrics/analyze.py   # git history → history/<today>.json
python3 tools/repo-metrics/render.py    # snapshots → index.html + report.md
```

Needs the full (unshallowed) history of `main`; `analyze.py` warns if the
clone is shallow. The `.github/workflows/repo-metrics.yml` workflow runs this
monthly, commits the refresh with `[skip ci]`, and publishes the dashboard to
GitHub Pages (one-time setup: Settings → Pages → Source: "GitHub Actions").

## What the numbers mean

- **Unit of work** — one first-parent commit on `main`: a squash-merged PR,
  a pre-squash-era merge commit, or an early direct commit. `release-please`
  version-bump PRs are excluded from work counts.
- **Code lines** — numstat totals excluding generated files (lockfiles,
  `CHANGELOG.md`) and `data/`; Markdown counts as docs, not code.
- **Regression fix** — a `fix` landing ≤7 days after a `feat` with the same
  scope or touching a shared code file. A proxy for "done wasn't done", not
  a verdict on any individual PR.
- **Fix chain** — ≥2 fixes on one scope with ≤7-day gaps between them.
- **Hotfix release** — a patch release tagged <24 h after the previous
  release (production-incident proxy).
- **Process timeline** — dated process-change events mined from the
  first/last commit touching each marker file (`MILESTONES` in
  `analyze.py`), aligned with monthly fix:feat. Add a row to `MILESTONES`
  whenever a new practice gets a marker file, so "did this change help?"
  stays answerable from a fresh run rather than a one-off git dig.

Tune thresholds and file classification at the top of `analyze.py`.
