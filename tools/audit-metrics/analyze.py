#!/usr/bin/env python3
"""Extract audit-trend metrics from docs/audits/ reports and the worktree.

Companion to tools/repo-metrics/ (same conventions: stdlib only, dated JSON
snapshots, render.py turns history into a report + dashboard). Where
repo-metrics mines git history for productivity, this tool tracks the
*adversarial audit* trend over time:

- open findings per audit report (by severity, category, and status), and a
  single weighted risk score per report so the trend is one line;
- the "hotspot watch": line counts of the files the audits flagged as
  monoliths or drift magnets;
- hygiene counters: cheap greppable proxies for audit findings (sync HTTP
  clients in the API, runBlocking on Android, suppressed lint, TODO/FIXME,
  cruft files, docker-compose variants);
- test-surface counts per area.

Usage: python3 tools/audit-metrics/analyze.py [--repo-root PATH] [--as-of YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

# Weighted risk score per open finding. The absolute number is arbitrary;
# only the trend between snapshots matters.
SEVERITY_WEIGHTS = {"CRITICAL": 10, "HIGH": 5, "MEDIUM": 2, "LOW": 1}

# Finding IDs encode their category by prefix letter (see AUDIT_PLAYBOOK.md).
CATEGORIES = {
    "A": "architectural_debt",
    "E": "edge_case_failures",
    "S": "scalability_bottlenecks",
    "D": "doc_test_gaps",
    "O": "operational_security",
}

# Files the audits flagged as monoliths, drift copies, or oversized
# workflows. Shrinking (or deleting) these is the point; growth is a
# regression. Missing files report null — a deleted hotspot is a win, not
# an error. Keep in sync with the parity ledger in docs/AUDIT_PLAYBOOK.md.
HOTSPOTS = [
    "frontend/src/app/[locale]/ChatIsland.tsx",  # A2 monolith
    "frontend/src/lib/api.ts",  # A4 duplicated plumbing
    "frontend/src/lib/verseExtraction.ts",  # A1 parser copy (web)
    "frontend/src/lib/versePatterns.ts",  # A1 parser copy (web)
    "android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt",  # A3
    "android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt",  # A1
    "android/app/src/main/kotlin/org/voxquieta/app/utils/LocalizedBookToEnglish.kt",  # A1 parity copy
    "api/chat/service.py",  # backend service monolith
    "api/utils/security.py",  # content-filter monolith
    ".github/workflows/azure-deploy.yml",  # O6 workflow monolith
]

# (name, root, filename regex, content regex). Each counter is a grep-cheap
# proxy for an audit finding; the finding ID it tracks is in the comment.
HYGIENE_COUNTERS = [
    ("api_sync_httpx_client", "api", r"\.py$", r"httpx\.Client\("),  # S1
    ("api_broad_except", "api", r"\.py$", r"except Exception\b|except\s*:"),
    ("api_noqa", "api", r"\.py$", r"#\s*noqa"),
    ("frontend_eslint_disable", "frontend/src", r"\.(ts|tsx)$", r"eslint-disable"),
    ("frontend_ts_suppress", "frontend/src", r"\.(ts|tsx)$", r"@ts-(ignore|expect-error)"),
    ("android_run_blocking", "android/app/src/main", r"\.kt$", r"\brunBlocking\b"),  # S6
    ("android_suppress", "android/app/src/main", r"\.kt$", r"@Suppress\("),
    ("todo_fixme_hack", ".", r"\.(py|ts|tsx|kt|kts|sh|sql|tf)$", r"\b(TODO|FIXME|HACK)\b"),
]

# Mirrors tools/repo-metrics/analyze.py CRUFT_PATTERNS / TEST_HINTS so the
# two tools classify files the same way.
CRUFT_PATTERNS = re.compile(r"(\.old(\.|$)|\.backup$|\.bak$|~$|\.orig$)")
TEST_HINTS = re.compile(
    r"(^|/)(tests?|__tests__|androidTest|screenshotTest)(/|$)"
    r"|(^|/)test_[^/]+$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$"
)

# Source areas for LOC + test-file counts: (area, root, filename regex).
AREAS = [
    ("api", "api", r"\.py$"),
    ("frontend", "frontend/src", r"\.(ts|tsx)$"),
    ("android", "android/app/src", r"\.(kt|kts)$"),
]

SKIP_DIRS = {"node_modules", ".next", ".venv", "venv", "__pycache__", "build", ".gradle", "dist"}

FINDING_HEADING = re.compile(r"^###\s+([A-Z]\d+)\s+[—-]", re.MULTILINE)
SEVERITY_LINE = re.compile(r"\*\*\[SEVERITY\]:?\*\*:?\s*(CRITICAL|HIGH|MEDIUM|LOW)")
STATUS_LINE = re.compile(r"\*\*\[STATUS\]:?\*\*:?\s*(NEW|STILL OPEN|RESOLVED)")
REPORT_NAME = re.compile(r"^(\d{4}-\d{2})-adversarial-audit(-\d+)?\.md$")


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def parse_report(path: Path) -> dict:
    """Split a report into finding blocks and tally severity/category/status.

    A finding is a `### <ID> — title` heading followed by a bullet list with
    a [SEVERITY] line and (from the second audit on) a [STATUS] line.
    Findings marked RESOLVED count toward `resolved`, not toward open totals.
    """
    text = path.read_text(encoding="utf-8")
    headings = list(FINDING_HEADING.finditer(text))
    open_by_severity = {s: 0 for s in SEVERITY_WEIGHTS}
    open_by_category = {c: 0 for c in CATEGORIES.values()}
    open_ids: list[str] = []
    resolved_ids: list[str] = []
    status_counts = {"NEW": 0, "STILL OPEN": 0, "RESOLVED": 0, "UNMARKED": 0}

    for i, h in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[h.start():end]
        fid = h.group(1)
        sev = SEVERITY_LINE.search(block)
        status_m = STATUS_LINE.search(block)
        status = status_m.group(1) if status_m else "UNMARKED"
        status_counts[status] += 1
        if status == "RESOLVED":
            resolved_ids.append(fid)
            continue
        if not sev:
            # A finding heading with no [SEVERITY] line and no RESOLVED status
            # is template drift — the whole point of this tool is to be the
            # machine check on the tallies, so fail loud instead of silently
            # dropping the finding and reporting a false count.
            raise ValueError(
                f"{path.name}: finding '{fid}' has a heading but no "
                f"[SEVERITY] line (status={status}). Fix the report, or "
                f"update SEVERITY_LINE/STATUS_LINE in analyze.py if the "
                f"report template changed."
            )
        open_ids.append(fid)
        open_by_severity[sev.group(1)] += 1
        category = CATEGORIES.get(fid[0])
        if category:
            open_by_category[category] += 1

    score = sum(SEVERITY_WEIGHTS[s] * n for s, n in open_by_severity.items())
    return {
        "file": path.name,
        "month": REPORT_NAME.match(path.name).group(1),
        "open_by_severity": open_by_severity,
        "open_by_category": open_by_category,
        "open_total": len(open_ids),
        "open_ids": open_ids,
        "resolved_ids": resolved_ids,
        "status_counts": status_counts,
        "risk_score": score,
    }


def collect_reports(repo: Path) -> list[dict]:
    audits = repo / "docs" / "audits"
    reports = sorted(p for p in audits.glob("*.md") if REPORT_NAME.match(p.name))
    return [parse_report(p) for p in reports]


def iter_files(root: Path, name_re: re.Pattern) -> list[Path]:
    out = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if name_re.search(p.name):
            out.append(p)
    return out


def count_lines(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))


def hotspot_sizes(repo: Path) -> dict:
    return {
        rel: (count_lines(repo / rel) if (repo / rel).is_file() else None)
        for rel in HOTSPOTS
    }


def hotspot_moves(repo: Path) -> dict:
    """For each missing hotspot, guess whether it was removed or just moved.

    A missing hotspot is only a "win" if the code is actually gone. The common
    refactor for a monolith is a rename or split, which leaves the trend line
    lying. Cheap heuristic: if a tracked file with the same basename exists at
    a different path, the hotspot likely moved there — surface the candidates
    rather than celebrating a deletion. Splits into differently-named files
    still read as "removed" (a documented limitation).
    """
    tracked = run_git(repo, "ls-files").splitlines()
    moves = {}
    for rel in HOTSPOTS:
        if (repo / rel).is_file():
            continue
        base = rel.rsplit("/", 1)[-1]
        candidates = [t for t in tracked if t.rsplit("/", 1)[-1] == base and t != rel]
        if candidates:
            moves[rel] = candidates
    return moves


def hygiene(repo: Path) -> dict:
    out = {}
    for name, root, name_pat, content_pat in HYGIENE_COUNTERS:
        name_re, content_re = re.compile(name_pat), re.compile(content_pat)
        total = 0
        base = repo / root
        if base.is_dir():
            for f in iter_files(base, name_re):
                if root == "." and (repo / "docs") in f.parents:
                    continue  # prose TODOs in docs/stories are not code debt
                total += len(content_re.findall(f.read_text(encoding="utf-8", errors="replace")))
        out[name] = total

    tracked = run_git(repo, "ls-files").splitlines()
    out["cruft_files"] = sum(1 for t in tracked if CRUFT_PATTERNS.search(t))
    out["compose_variants"] = sum(
        1 for t in tracked if re.fullmatch(r"docker-compose[^/]*\.ya?ml", t)
    )
    return out


def loc_and_tests(repo: Path) -> dict:
    out = {}
    for area, root, name_pat in AREAS:
        name_re = re.compile(name_pat)
        src_lines = test_lines = src_files = test_files = 0
        base = repo / root
        for f in iter_files(base, name_re) if base.is_dir() else []:
            rel = f.relative_to(repo).as_posix()
            n = count_lines(f)
            if TEST_HINTS.search(rel):
                test_lines += n
                test_files += 1
            else:
                src_lines += n
                src_files += 1
        out[area] = {
            "src_lines": src_lines, "src_files": src_files,
            "test_lines": test_lines, "test_files": test_files,
        }
    e2e = repo / "frontend" / "e2e"
    out["frontend_e2e_specs"] = (
        len(list(e2e.glob("*.spec.ts"))) if e2e.is_dir() else 0
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=None)
    ap.add_argument("--as-of", default=None, help="snapshot date (YYYY-MM-DD), default today")
    args = ap.parse_args()

    repo = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parents[2]
    as_of = args.as_of or dt.date.today().isoformat()

    reports = collect_reports(repo)
    if not reports:
        raise SystemExit("no audit reports found under docs/audits/ — run /risk-audit first")

    # Store only what a snapshot needs: the latest report's tallies plus a
    # running resolved counter. Embedding the full parsed history in every
    # dated file (the workflow writes one monthly + on every audit) would
    # re-store the whole growing corpus forever — unbounded git bloat. The
    # cumulative-resolved figure is recomputed here from all reports each run,
    # so the snapshot keeps a single int, not the list.
    snapshot = {
        "generated": as_of,
        "commit": run_git(repo, "rev-parse", "--short", "HEAD").strip(),
        "report": reports[-1],
        "latest_report": reports[-1]["month"],
        "risk_score": reports[-1]["risk_score"],
        "resolved_cumulative": sum(len(r["resolved_ids"]) for r in reports),
        "hotspots": hotspot_sizes(repo),
        "hotspot_moves": hotspot_moves(repo),
        "hygiene": hygiene(repo),
        "areas": loc_and_tests(repo),
    }

    out_dir = repo / "docs" / "audits" / "metrics" / "history"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{as_of}.json"
    out_path.write_text(json.dumps(snapshot, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out_path} (risk score {snapshot['risk_score']}, "
          f"{reports[-1]['open_total']} open findings in {reports[-1]['month']})")


if __name__ == "__main__":
    main()
