#!/usr/bin/env python3
"""Render docs/metrics/index.html (dashboard) and docs/metrics/report.md
from the JSON snapshots produced by analyze.py. Stdlib only.

The dashboard is fully self-contained (inline CSS/JS/data, no CDN) so it
works as a committed file opened locally, on GitHub Pages, and in any
CSP-restricted viewer. Light/dark theme follows prefers-color-scheme and
honors an explicit data-theme attribute on <html>.

Usage: python3 tools/repo-metrics/render.py [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TYPE_GROUPS = ["feat", "fix", "build", "ci", "docs", "other"]

# Short background notes for models seen in Co-Authored-By trailers or harness
# configs. Keyed by prefix match against the attribution label / model string.
MODEL_INFO = {
    "Claude Opus 4.5": "Anthropic's frontier Opus-tier model (released Nov 2025) — the strongest reasoning/agentic tier of its generation; workhorse of this repo's pre-launch phase.",
    "Claude Opus 4.6": "Opus-tier successor (early 2026) with adaptive thinking and a 1M-token context window; used in the later phase and as the opencode orchestrator.",
    "Claude Sonnet 4.5": "Mid-tier Anthropic model balancing speed and capability; used for implementation-heavy subtasks.",
    "Claude Sonnet 4.6": "Sonnet-tier successor (early 2026); the 'build' model in the Plan→Build→Verify relay documented in AGENTS.md.",
    "Claude (unversioned)": "Commits co-authored as plain 'Claude' via Claude Code before version names were recorded in trailers.",
    "Claude (moonshotai/kimi-k2.5)": "A third-party model (Moonshot Kimi K2.5) driven through a Claude-Code-style harness.",
    "GitHub Copilot": "GitHub's autonomous coding agent (copilot-swe-agent) — assigned issues/PRs directly on GitHub.",
    "Android Dev alias": "Commit persona used by the opencode Android subagents (android-dev@bibleinspiration.app).",
    "opencode/minimax-m2.5-free": "MiniMax M2.5 via the opencode gateway — implementation model for opencode specialist subagents.",
    "openrouter/qwen/qwen3-coder": "Alibaba Qwen3-Coder via OpenRouter — the opencode android-gemini subagent's model.",
    "github-copilot/claude-opus-4.6": "Claude Opus 4.6 accessed through the GitHub Copilot provider — the opencode orchestrator model.",
}
GROUP_OF = {
    "feat": "feat", "fix": "fix", "build": "build", "ci": "ci", "docs": "docs",
}


def group_type(t: str) -> str:
    return GROUP_OF.get(t, "other")


def load_history(history_dir: Path) -> list[dict]:
    snaps = []
    for p in sorted(history_dir.glob("*.json")):
        try:
            snaps.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    if not snaps:
        raise SystemExit(f"no snapshots in {history_dir} — run analyze.py first")
    return snaps


def fmt(n) -> str:
    if n is None:
        return "—"
    if isinstance(n, float):
        return f"{n:,.2f}".rstrip("0").rstrip(".")
    return f"{n:,}"


# --------------------------------------------------------------------------
# report.md
# --------------------------------------------------------------------------

def render_report(m: dict, snaps: list[dict], repo_url: str) -> str:
    t = m["totals"]
    pre, post = m["phases"]["pre_launch"], m["phases"]["post_launch"]
    L: list[str] = []
    add = L.append

    add("# Repo productivity report")
    add("")
    add(f"*Generated {m['generated']} by `tools/repo-metrics/` — history "
        f"{m['range']['first']} → {m['range']['last']}. Interactive dashboard: "
        f"[index.html](./index.html).*")
    add("")
    add("## Headline")
    add("")
    add("| Metric | Value |")
    add("|---|---|")
    add(f"| Units of work landed on main (PRs + direct commits, release bumps excluded) | **{fmt(t['units'])}** |")
    add(f"| Calendar span | {fmt(t['calendar_days'])} days ({fmt(t['active_days'])} active — {t['active_days']/t['calendar_days']:.0%}) |")
    add(f"| Code lines added / deleted | +{fmt(t['added_code'])} / −{fmt(t['deleted_code'])} (net +{fmt(t['net_code'])}) |")
    add(f"| Releases shipped | {fmt(t['releases'])} |")
    add(f"| fix : feat ratio | **{t['fix_per_feat']}** |")
    add(f"| Same-day hotfix releases (<24h after previous) | {fmt(t['hotfix_releases'])} |")
    add(f"| Regression fixes (fix ≤7 days after related feat) | {fmt(t['regression_fixes'])} "
        f"({fmt(t['regression_fixes_same_scope'])} same-scope) |")
    add(f"| Fix chains (≥2 fixes, same scope, ≤7-day gaps) | {fmt(t['fix_chain_count'])} |")
    add(f"| Reverts | {fmt(t['reverts'])} |")
    add("")

    add("## Velocity")
    add("")
    add("| Phase | Units | Active days | Units/active day | feat | fix | fix:feat | Code +/− |")
    add("|---|---|---|---|---|---|---|---|")
    for name, p in (("Pre-launch (→ v0.1.0, %s)" % m["launch_date"], pre),
                    ("Post-launch", post)):
        if p:
            add(f"| {name} | {fmt(p['units'])} | {fmt(p['active_days'])}/{fmt(p['days'])} "
                f"| {p['units_per_active_day']} | {fmt(p['feat'])} | {fmt(p['fix'])} "
                f"| {p['fix_per_feat']} | +{fmt(p['added_code'])} / −{fmt(p['deleted_code'])} |")
    add("")
    add("Work landed by type:")
    add("")
    add("| Type | Count |")
    add("|---|---|")
    for typ, n in m["types"].items():
        add(f"| {typ} | {fmt(n)} |")
    add("")

    add("## Churn & rework")
    add("")
    add(f"Overall churn ratio (deleted/added code lines): **{t['churn_ratio']}** — "
        f"{t['churn_ratio']:.0%} of written code was later removed or rewritten.")
    add("")
    add("Top fix chains (bursts of fixes on one scope):")
    add("")
    add("| Scope | Fixes | Window | PRs |")
    add("|---|---|---|---|")
    for c in m["fix_chains"][:10]:
        prs = ", ".join(f"[#{p}]({repo_url}/pull/{p})" if p else "—" for p in c["prs"][:8])
        more = f" +{len(c['prs'])-8} more" if len(c["prs"]) > 8 else ""
        add(f"| {c['scope']} | {c['count']} | {c['start']} → {c['end']} | {prs}{more} |")
    add("")
    add("Hotspot files (code files touched by the most units of work):")
    add("")
    add("| File | Changes |")
    add("|---|---|")
    for h in m["hotspots"][:15]:
        add(f"| `{h['path']}` | {h['changes']} |")
    add("")

    add("## Quality & errors")
    add("")
    add("Monthly fix vs feat:")
    add("")
    add("| Month | feat | fix | fix:feat |")
    add("|---|---|---|---|")
    for row in m["monthly_fix_feat"]:
        ratio = round(row["fix"] / row["feat"], 2) if row["feat"] else "—"
        add(f"| {row['month']} | {row['feat']} | {row['fix']} | {ratio} |")
    add("")
    add(f"Production-incident proxies: {fmt(t['hotfix_releases'])} same-day hotfix "
        f"releases out of {fmt(t['releases'])} total; {fmt(t['reverts'])} reverts.")
    add("")
    if m["reverts"]:
        for r in m["reverts"]:
            pr = f"[#{r['pr']}]({repo_url}/pull/{r['pr']})" if r["pr"] else ""
            add(f"- {r['date']} revert: {r['desc']} {pr}")
        add("")
    add("Most bug-prone scopes (by fix count):")
    add("")
    add("| Scope | Total units | feat | fix |")
    add("|---|---|---|---|")
    bug_prone = sorted(m["scopes"], key=lambda s: -s.get("fix", 0))[:10]
    for s in bug_prone:
        add(f"| {s['scope']} | {s['total']} | {s.get('feat', 0)} | {s.get('fix', 0)} |")
    add("")

    add("## Models & harness")
    add("")
    a = m.get("attribution")
    if a:
        share = a["attributed_ai_commits"] / max(a["total_commits"] - a["bot_commits"], 1)
        add(f"Of {fmt(a['total_commits'])} commits in the full graph, "
            f"{fmt(a['bot_commits'])} are automation bots; of the rest, "
            f"**{fmt(a['attributed_ai_commits'])} ({share:.0%}) carry an AI "
            f"co-author trailer**. {a['note']}")
        add("")
        add("| Model / author | Commits | feat | fix | About |")
        add("|---|---|---|---|---|")
        for r in a["by_label"]:
            info = MODEL_INFO.get(r["label"], "")
            add(f"| {r['label']} | {fmt(r['commits'])} | {r['feat']} | {r['fix']} | {info} |")
        add("")
    for h in m.get("harnesses", []):
        add(f"- **{h['name']}** — {h['evidence']}."
            + (f" Models: {', '.join(h['models'])}." if h["models"] else ""))
    add("")

    add("## Codebase health")
    add("")
    add("| Component | Files | LOC | Test files | Test LOC |")
    add("|---|---|---|---|---|")
    for name, c in m["snapshot"]["components"].items():
        add(f"| {name} | {fmt(c['files'])} | {fmt(c['loc'])} | {fmt(c['test_files'])} | {fmt(c['test_loc'])} |")
    add("")
    if m["snapshot"]["cruft"]:
        add("Leftover cruft (candidates for deletion):")
        add("")
        for path in m["snapshot"]["cruft"]:
            add(f"- `{path}`")
        add("")

    if len(snaps) > 1:
        add("## Run-over-run")
        add("")
        add("| Snapshot | Units | fix:feat | Net code LOC | Releases | Regression fixes |")
        add("|---|---|---|---|---|---|")
        for s in snaps:
            st = s["totals"]
            add(f"| {s['generated']} | {fmt(st['units'])} | {st['fix_per_feat']} "
                f"| {fmt(st['net_code'])} | {fmt(st['releases'])} | {fmt(st['regression_fixes'])} |")
        add("")

    add("## Methodology")
    add("")
    add("- One *unit of work* = one first-parent commit on `main`: a squash-merged PR, "
        "a merge commit (pre-squash era), or a direct commit (earliest era). "
        "`release-please` version-bump PRs are excluded from work counts.")
    add("- Line counts exclude generated files (lockfiles, CHANGELOG) and `data/`; "
        "docs (`.md`) are counted separately from code.")
    add("- *Regression fix* = a `fix` landing ≤7 days after a `feat` with the same "
        "scope or touching a shared code file — a proxy, not a verdict.")
    add("- *Hotfix release* = a patch release tagged <24 h after the previous release.")
    add("- Regenerate with `make repo-metrics`.")
    add("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# dashboard payload
# --------------------------------------------------------------------------

def dashboard_payload(m: dict, snaps: list[dict], repo_url: str) -> dict:
    """Shape exactly what the dashboard JS needs."""
    weekly = []
    cumulative = 0
    for w in m["weekly"]:
        units = {g: 0 for g in TYPE_GROUPS}
        for typ, n in w["units"].items():
            units[group_type(typ)] += n
        cumulative += w["added_code"] - w["deleted_code"]
        weekly.append({
            "week": w["week"], "units": units,
            "added": w["added_code"], "deleted": w["deleted_code"],
            "cum_net": cumulative, "active_days": w["active_days"],
        })
    rel_weekly: dict[str, dict] = {}
    for r in m["releases"]:
        if not r.get("tagged_at"):
            continue
        import datetime as dt
        d = dt.date.fromisoformat(r["tagged_at"][:10])
        wk = (d - dt.timedelta(days=d.weekday())).isoformat()
        slot = rel_weekly.setdefault(wk, {"minor": 0, "patch": 0, "hotfix": 0})
        slot["patch" if r["level"] == "patch" else "minor"] += 1
        if r["level"] == "patch" and (r["hours_since_prev"] or 99) < 24:
            slot["hotfix"] += 1
    monthly = [
        {"month": r["month"], "feat": r["feat"], "fix": r["fix"],
         "ratio": round(r["fix"] / r["feat"], 2) if r["feat"] else None}
        for r in m["monthly_fix_feat"]
    ]
    return {
        "generated": m["generated"],
        "range": m["range"],
        "launch": m["launch_date"],
        "repoUrl": repo_url,
        "totals": m["totals"],
        "types": m["types"],
        "weekly": weekly,
        "relWeekly": rel_weekly,
        "monthly": monthly,
        "phases": m["phases"],
        "chains": m["fix_chains"][:8],
        "regressions": sorted(m["regressions"], key=lambda r: r["days"])[:10],
        "hotspots": m["hotspots"][:15],
        "components": m["snapshot"]["components"],
        "cruft": m["snapshot"]["cruft"],
        "hotfixes": m["hotfixes"],
        "reverts": m["reverts"],
        "attribution": m.get("attribution"),
        "harnesses": m.get("harnesses", []),
        "modelInfo": MODEL_INFO,
        "runs": [{"generated": s["generated"], **{k: s["totals"].get(k) for k in
                  ("units", "fix_per_feat", "net_code", "releases",
                   "regression_fixes")}} for s in snaps],
    }


DOC_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { margin: 0; background: #f9f9f7; }
  @media (prefers-color-scheme: dark) { body { background: #0d0d0d; } }
</style>
</head>
<body>
"""
DOC_TAIL = "</body>\n</html>\n"


def render_dashboard(payload: dict, wrap: bool = True) -> str:
    """Fill the template with data. wrap=True produces a complete HTML
    document (committed file / Pages); wrap=False keeps the bare fragment
    (for CSP-wrapped viewers that add their own document skeleton)."""
    template = (Path(__file__).parent / "dashboard_template.html").read_text(encoding="utf-8")
    data = json.dumps(payload, separators=(",", ":"))
    body = template.replace("/*__DATA__*/null", data)
    return DOC_HEAD + body + DOC_TAIL if wrap else body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", type=Path)
    ap.add_argument("--repo-url",
                    default="https://github.com/zioalex/getinspiredbythebible")
    args = ap.parse_args()
    repo = args.repo_root.resolve()
    out_dir = repo / "docs" / "metrics"
    snaps = load_history(out_dir / "history")
    latest = snaps[-1]

    report = render_report(latest, snaps, args.repo_url)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    payload = dashboard_payload(latest, snaps, args.repo_url)
    html = render_dashboard(payload)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"wrote {out_dir / 'report.md'} and {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
