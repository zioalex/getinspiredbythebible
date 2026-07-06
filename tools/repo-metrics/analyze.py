#!/usr/bin/env python3
"""Extract repo productivity metrics from git history and CHANGELOG.md.

Produces a dated JSON snapshot under docs/metrics/history/ that render.py
turns into the dashboard and report. Stdlib only — no dependencies.

Data model: `main` is squash-merged since ~PR #520 (one commit = one PR,
conventional subject + "(#NNN)"); before that PRs landed as merge commits
("Merge pull request #NNN from owner/branch") and the earliest work as
direct commits. We walk `--first-parent` so each mainline entry is one
unit of landed work, and recover type/scope/PR number from whichever
convention the entry uses.

Usage: python3 tools/repo-metrics/analyze.py [--repo-root PATH] [--as-of YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

FIELD_SEP = "\x02"
RECORD_SEP = "\x01"

CONV_TYPES = {
    "feat", "fix", "perf", "revert", "docs", "chore", "build", "ci",
    "refactor", "test", "style", "merge",
}

# File-path buckets. "generated" churn (lockfiles, release-please output) is
# excluded from code-churn numbers so it doesn't drown real work.
GENERATED_FILES = {"CHANGELOG.md", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
GENERATED_SUFFIXES = (".lock", ".lockfile", "-lock.json", "-lock.yaml")
DATA_DIRS = ("data/", "multiple_embeddings/")

CRUFT_PATTERNS = re.compile(r"(\.old(\.|$)|\.backup$|\.bak$|~$|\.orig$)")

TEST_HINTS = re.compile(
    r"(^|/)(tests?|__tests__|androidTest|screenshotTest)(/|$)"
    r"|(^|/)test_[^/]+$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$"
)

CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".kt", ".kts",
    ".java", ".sql", ".sh", ".css", ".scss", ".html", ".tf", ".yml",
    ".yaml", ".toml", ".gradle", ".pro", ".xml", ".json", ".Dockerfile",
}


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def classify_path(path: str) -> str:
    """Bucket a repo path: code | docs | data | generated."""
    name = path.rsplit("/", 1)[-1]
    if name in GENERATED_FILES or name.endswith(GENERATED_SUFFIXES):
        return "generated"
    if path.startswith(DATA_DIRS):
        return "data"
    if name.lower().endswith((".md", ".rst", ".txt")):
        return "docs"
    return "code"


def component_of(path: str) -> str:
    top = path.split("/", 1)[0]
    if top in {"api", "frontend", "android", "scripts", "docs", "tools"}:
        return top
    if top in {"infra", "deployment"} or top.startswith("docker-compose"):
        return "infra"
    if top == ".github":
        return "ci"
    if top in {"data", "multiple_embeddings"}:
        return "data"
    return "root"


CONV_RE = re.compile(r"^(?P<type>[a-z]+)(\((?P<scope>[^)]*)\))?!?:\s*(?P<desc>.*)$")
PR_TAIL_RE = re.compile(r"\(#(?P<pr>\d+)\)\s*$")
MERGE_RE = re.compile(r"^Merge pull request #(?P<pr>\d+) from [^/]+/(?P<branch>.+)$")
RELEASE_RE = re.compile(r"^release \d+\.\d+\.\d+")


def parse_subject(subject: str) -> dict:
    """Recover type/scope/pr/description from any of the three eras."""
    pr = None
    m = PR_TAIL_RE.search(subject)
    if m:
        pr = int(m.group("pr"))
        subject_body = subject[: m.start()].rstrip()
    else:
        subject_body = subject

    merge = MERGE_RE.match(subject)
    if merge:
        pr = int(merge.group("pr"))
        branch = merge.group("branch")
        prefix = branch.split("/", 1)[0].lower()
        if branch.startswith("dependabot/"):
            ctype = "build"
        elif prefix in CONV_TYPES:
            ctype = prefix
        else:
            ctype = "other"
        return {"type": ctype, "scope": None, "pr": pr, "desc": branch}

    conv = CONV_RE.match(subject_body)
    if conv and conv.group("type") in CONV_TYPES:
        ctype = conv.group("type")
        scope = conv.group("scope") or None
        desc = conv.group("desc")
        if ctype == "chore" and RELEASE_RE.match(desc):
            ctype = "release"  # release-please version bumps, tracked apart
        return {"type": ctype, "scope": scope, "pr": pr, "desc": desc}

    return {"type": "other", "scope": None, "pr": pr, "desc": subject_body}


def collect_units(repo: Path, branch: str) -> list[dict]:
    log = run_git(
        repo, "log", branch, "--first-parent", "--diff-merges=first-parent",
        "--numstat", "--date=iso-strict",
        f"--format={RECORD_SEP}%H{FIELD_SEP}%aI{FIELD_SEP}%s",
    )
    units = []
    for record in log.split(RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        header, _, body = record.partition("\n")
        sha, date_iso, subject = header.split(FIELD_SEP, 2)
        parsed = parse_subject(subject)
        files, added, deleted = [], Counter(), Counter()
        for line in body.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            a, d, path = parts
            if "=>" in path:  # rename syntax "old => new" / "dir/{a => b}/f"
                path = re.sub(r"\{?([^{]*) => ([^}]*)\}?", r"\2", path)
                path = path.replace("//", "/")
            bucket = classify_path(path)
            files.append(path)
            if a != "-":
                added[bucket] += int(a)
            if d != "-":
                deleted[bucket] += int(d)
        units.append({
            "sha": sha,
            "date": date_iso,
            "subject": subject,
            "type": parsed["type"],
            "scope": parsed["scope"],
            "pr": parsed["pr"],
            "desc": parsed["desc"],
            "files": files,
            "added": dict(added),
            "deleted": dict(deleted),
        })
    units.reverse()  # oldest first
    return units


def parse_changelog(repo: Path) -> list[dict]:
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    header_re = re.compile(
        r"^## \[(?P<ver>\d+\.\d+\.\d+)\][^\n]*?(\((?P<date>\d{4}-\d{2}-\d{2})\))?\s*$",
        re.M,
    )
    section_re = re.compile(r"^### (?P<name>.+)$", re.M)
    releases = []
    matches = list(header_re.finditer(text))
    for i, m in enumerate(matches):
        body = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        sections: dict[str, int] = {}
        sec_matches = list(section_re.finditer(body))
        for j, sm in enumerate(sec_matches):
            sec_body = body[sm.end(): sec_matches[j + 1].start() if j + 1 < len(sec_matches) else len(body)]
            bullets = len(re.findall(r"^\* ", sec_body, re.M))
            sections[sm.group("name")] = bullets
        major, minor, patch = (int(x) for x in m.group("ver").split("."))
        level = "major" if minor == 0 and patch == 0 and major > 0 else (
            "minor" if patch == 0 else "patch")
        releases.append({
            "version": m.group("ver"),
            "date": m.group("date"),
            "level": level,
            "sections": sections,
        })
    releases.reverse()  # oldest first
    return releases


def tag_timestamps(repo: Path) -> dict[str, str]:
    out = run_git(repo, "for-each-ref", "refs/tags",
                  "--format=%(refname:short)%09%(creatordate:iso-strict)")
    stamps = {}
    for line in out.splitlines():
        tag, _, ts = line.partition("\t")
        stamps[tag.lstrip("v")] = ts
    return stamps


def snapshot_worktree(repo: Path) -> dict:
    files = run_git(repo, "ls-files").splitlines()
    components: dict[str, dict] = defaultdict(
        lambda: {"files": 0, "loc": 0, "test_files": 0, "test_loc": 0})
    cruft = []
    docs_loc = 0
    for path in files:
        if classify_path(path) == "data":
            comp = components["data"]
            comp["files"] += 1
            continue
        p = repo / path
        if not p.is_file():
            continue
        if CRUFT_PATTERNS.search(path):
            cruft.append(path)
        suffix = p.suffix or p.name
        is_text = suffix in CODE_EXTENSIONS or classify_path(path) == "docs" or "." not in p.name
        loc = 0
        if is_text:
            try:
                loc = sum(1 for _ in p.open("r", encoding="utf-8", errors="ignore"))
            except OSError:
                loc = 0
        comp = components[component_of(path)]
        comp["files"] += 1
        comp["loc"] += loc
        if classify_path(path) == "docs":
            docs_loc += loc
        if TEST_HINTS.search(path):
            comp["test_files"] += 1
            comp["test_loc"] += loc
    return {
        "components": dict(sorted(components.items())),
        "cruft": sorted(cruft),
        "docs_loc": docs_loc,
        "tracked_files": len(files),
    }


def iso_week_start(d: dt.date) -> str:
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def build_metrics(units: list[dict], releases: list[dict],
                  tags: dict[str, str], snapshot: dict, as_of: str) -> dict:
    def date_of(u: dict) -> dt.date:
        return dt.datetime.fromisoformat(u["date"]).date()

    work = [u for u in units if u["type"] != "release"]
    release_units = [u for u in units if u["type"] == "release"]

    # ---- weekly aggregation ----
    weekly: dict[str, dict] = defaultdict(lambda: {
        "units": Counter(), "added_code": 0, "deleted_code": 0,
        "added_docs": 0, "deleted_docs": 0, "active_days": set(),
    })
    for u in units:
        d = date_of(u)
        wk = weekly[iso_week_start(d)]
        wk["active_days"].add(d.isoformat())
        if u["type"] != "release":
            wk["units"][u["type"]] += 1
            wk["added_code"] += u["added"].get("code", 0)
            wk["deleted_code"] += u["deleted"].get("code", 0)
            wk["added_docs"] += u["added"].get("docs", 0)
            wk["deleted_docs"] += u["deleted"].get("docs", 0)
    weeks = []
    for start in sorted(weekly):
        w = weekly[start]
        weeks.append({
            "week": start,
            "units": dict(w["units"]),
            "added_code": w["added_code"],
            "deleted_code": w["deleted_code"],
            "added_docs": w["added_docs"],
            "deleted_docs": w["deleted_docs"],
            "active_days": len(w["active_days"]),
        })

    # ---- monthly fix:feat ----
    monthly = defaultdict(Counter)
    for u in work:
        monthly[u["date"][:7]][u["type"]] += 1
    monthly_fix_feat = [
        {"month": m, "fix": c.get("fix", 0), "feat": c.get("feat", 0)}
        for m, c in sorted(monthly.items())
    ]

    # ---- scopes ----
    scope_counter: dict[str, Counter] = defaultdict(Counter)
    for u in work:
        if u["scope"]:
            for s in re.split(r"[+,]", u["scope"]):
                s = s.strip()
                if s:
                    scope_counter[s][u["type"]] += 1
    scopes = sorted(
        ({"scope": s, "total": sum(c.values()), **{t: c[t] for t in c}}
         for s, c in scope_counter.items()),
        key=lambda x: -x["total"],
    )

    # ---- fix chains: >=2 fixes on the same scope within rolling 7 days ----
    fixes_by_scope: dict[str, list[dict]] = defaultdict(list)
    for u in work:
        if u["type"] == "fix" and u["scope"]:
            fixes_by_scope[u["scope"]].append(u)
    fix_chains = []
    for scope, fixes in fixes_by_scope.items():
        chain: list[dict] = []
        for u in fixes:
            if chain and (date_of(u) - date_of(chain[-1])).days > 7:
                if len(chain) >= 2:
                    fix_chains.append((scope, chain))
                chain = []
            chain.append(u)
        if len(chain) >= 2:
            fix_chains.append((scope, chain))
    fix_chains_out = sorted(
        ({"scope": s,
          "count": len(ch),
          "start": ch[0]["date"][:10],
          "end": ch[-1]["date"][:10],
          "prs": [u["pr"] for u in ch],
          "subjects": [u["desc"] for u in ch]}
         for s, ch in fix_chains),
        key=lambda x: -x["count"],
    )

    # ---- regressions: fix within 7 days of a feat sharing scope or a code file ----
    feats = [u for u in work if u["type"] == "feat"]
    regressions = []
    for u in work:
        if u["type"] != "fix":
            continue
        fix_files = {f for f in u["files"] if classify_path(f) == "code"}
        fix_date = date_of(u)
        for f in reversed(feats):
            gap = (fix_date - date_of(f)).days
            if gap < 0:
                continue
            if gap > 7:
                break
            same_scope = u["scope"] and f["scope"] and u["scope"] == f["scope"]
            shared = fix_files & {p for p in f["files"] if classify_path(p) == "code"}
            if same_scope or shared:
                regressions.append({
                    "fix_pr": u["pr"], "fix": u["desc"], "fix_date": u["date"][:10],
                    "feat_pr": f["pr"], "feat": f["desc"], "feat_date": f["date"][:10],
                    "days": gap,
                    "match": "scope" if same_scope else "files",
                })
                break

    # ---- hotspots: code files touched by the most units of work ----
    touch = Counter()
    for u in work:
        for f in set(u["files"]):
            if classify_path(f) == "code":
                touch[f] += 1
    hotspots = [{"path": p, "changes": n} for p, n in touch.most_common(25)]

    # ---- releases enriched with tag timestamps + hotfix detection ----
    rel_out = []
    prev_ts = None
    for r in releases:
        ts = tags.get(r["version"])
        hours_since_prev = None
        if ts and prev_ts:
            delta = dt.datetime.fromisoformat(ts) - dt.datetime.fromisoformat(prev_ts)
            hours_since_prev = round(delta.total_seconds() / 3600, 1)
        rel_out.append({**r, "tagged_at": ts, "hours_since_prev": hours_since_prev})
        if ts:
            prev_ts = ts
    hotfixes = [r for r in rel_out
                if r["level"] == "patch"
                and r["hours_since_prev"] is not None and r["hours_since_prev"] < 24]
    reverts = [u for u in work if u["type"] == "revert"
               or u["desc"].lower().startswith("revert")]

    # ---- pre/post-launch split ----
    launch_ts = tags.get("0.1.0")
    launch_date = launch_ts[:10] if launch_ts else "2026-05-03"
    pre = [u for u in work if u["date"][:10] < launch_date]
    post = [u for u in work if u["date"][:10] >= launch_date]

    def phase_stats(us: list[dict]) -> dict:
        if not us:
            return {}
        c = Counter(u["type"] for u in us)
        days = (date_of(us[-1]) - date_of(us[0])).days + 1
        active = len({u["date"][:10] for u in us})
        return {
            "units": len(us),
            "days": days,
            "active_days": active,
            "units_per_active_day": round(len(us) / active, 2),
            "feat": c.get("feat", 0),
            "fix": c.get("fix", 0),
            "fix_per_feat": round(c.get("fix", 0) / c.get("feat", 1), 2),
            "added_code": sum(u["added"].get("code", 0) for u in us),
            "deleted_code": sum(u["deleted"].get("code", 0) for u in us),
        }

    # ---- totals ----
    types = Counter(u["type"] for u in work)
    added_code = sum(u["added"].get("code", 0) for u in work)
    deleted_code = sum(u["deleted"].get("code", 0) for u in work)
    all_days = {u["date"][:10] for u in units}
    prs = [u["pr"] for u in units if u["pr"]]

    return {
        "schema": 1,
        "generated": as_of,
        "range": {"first": units[0]["date"][:10], "last": units[-1]["date"][:10]},
        "launch_date": launch_date,
        "totals": {
            "units": len(work),
            "release_prs": len(release_units),
            "prs_seen": len(prs),
            "max_pr": max(prs) if prs else None,
            "calendar_days": (date_of(units[-1]) - date_of(units[0])).days + 1,
            "active_days": len(all_days),
            "added_code": added_code,
            "deleted_code": deleted_code,
            "net_code": added_code - deleted_code,
            "churn_ratio": round(deleted_code / added_code, 3) if added_code else None,
            "fix_per_feat": round(types.get("fix", 0) / types.get("feat", 1), 2),
            "releases": len(rel_out),
            "hotfix_releases": len(hotfixes),
            "reverts": len(reverts),
            "regression_fixes": len(regressions),
            "regression_fixes_same_scope": sum(
                1 for r in regressions if r["match"] == "scope"),
            "fix_chain_count": len(fix_chains_out),
        },
        "types": dict(types.most_common()),
        "weekly": weeks,
        "monthly_fix_feat": monthly_fix_feat,
        "scopes": scopes[:30],
        "fix_chains": fix_chains_out[:20],
        "regressions": regressions,
        "hotspots": hotspots,
        "releases": rel_out,
        "hotfixes": [{"version": h["version"], "date": h["date"],
                      "hours_since_prev": h["hours_since_prev"]} for h in hotfixes],
        "reverts": [{"pr": u["pr"], "date": u["date"][:10], "desc": u["desc"]}
                    for u in reverts],
        "phases": {"pre_launch": phase_stats(pre), "post_launch": phase_stats(post)},
        "snapshot": snapshot,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", type=Path)
    ap.add_argument("--branch", default="origin/main",
                    help="analyze this ref (default origin/main — the local "
                         "main ref is often behind)")
    ap.add_argument("--as-of", default=dt.date.today().isoformat())
    ap.add_argument("--out-dir", default=None,
                    help="default: <repo>/docs/metrics/history")
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    if run_git(repo, "rev-parse", "--is-shallow-repository").strip() == "true":
        print("WARNING: shallow clone — history is incomplete; "
              "run `git fetch --unshallow origin` first")
    units = collect_units(repo, args.branch)
    releases = parse_changelog(repo)
    tags = tag_timestamps(repo)
    snapshot = snapshot_worktree(repo)
    metrics = build_metrics(units, releases, tags, snapshot, args.as_of)

    out_dir = Path(args.out_dir) if args.out_dir else repo / "docs" / "metrics" / "history"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.as_of}.json"
    out_path.write_text(json.dumps(metrics, indent=1) + "\n", encoding="utf-8")
    t = metrics["totals"]
    print(f"wrote {out_path}")
    print(f"  units={t['units']} (+{t['release_prs']} release PRs), "
          f"releases={t['releases']}, fix/feat={t['fix_per_feat']}, "
          f"code +{t['added_code']}/-{t['deleted_code']}")


if __name__ == "__main__":
    main()
