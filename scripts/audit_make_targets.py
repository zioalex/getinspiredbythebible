#!/usr/bin/env python3
"""Reproducible audit of every Makefile target (BITB-220).

Standard library only. Nothing here runs a real recipe: the Makefile is inspected
with `make -pRrq` (rule database) and `make -n` (dry run), so no docker, cloud,
network or install target can fire.

    python3 scripts/audit_make_targets.py --list     # target inventory, no classification needed
    python3 scripts/audit_make_targets.py --check    # invariants + docs/MAKE_TARGET_AUDIT.md is current
    python3 scripts/audit_make_targets.py --write    # regenerate docs/MAKE_TARGET_AUDIT.md

Hand-maintained judgement (safety class, how a target was verified, defects) lives in
scripts/make_target_audit.json; this tool refuses to pass if a Makefile target is missing
from it, so the inventory cannot silently rot when a target is added.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"
CLASSIFICATION = ROOT / "scripts" / "make_target_audit.json"
REPORT = ROOT / "docs" / "MAKE_TARGET_AUDIT.md"

SAFETY_CLASSES = (
    "read-only",
    "local-write",
    "local-docker",
    "local-destructive",
    "network-read",
    "cloud-read",
    "cloud-mutating",
    "cloud-destructive",
)
EXECUTION = ("real", "mocked", "static")

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# `make` may be followed by option words; the target is the first non-option word.
DOC_REF_RE = re.compile(r"\bmake\s+(?:-[A-Za-z-]+\s+)*([a-z][a-z0-9]*(?:-[a-z0-9]+)+|[a-z]+)\b")
PATH_RE = re.compile(
    r"(?<![\w./$-])((?:scripts|tools|k8s|deployment|docs|\.github|android|api|frontend)/[\w./-]*[\w]"
    r"|docker-compose[\w.-]*\.yml)"
)


@dataclass
class Target:
    name: str
    line: int = 0
    phony: bool = False
    prereqs: list[str] = field(default_factory=list)
    has_recipe: bool = False
    in_help: bool = False
    help_text: str = ""
    recipe: list[str] = field(default_factory=list)


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    # A parent `make` (or `make test-makefile`) leaks these and would change what we inspect.
    for key in ("MAKEFLAGS", "MAKELEVEL", "MFLAGS", "MAKEOVERRIDES"):
        env.pop(key, None)
    env["LC_ALL"] = "C"
    return env


def _make(args: list[str], root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "-f", "Makefile", *args],
        cwd=root,
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def load_targets(root: Path = ROOT) -> dict[str, Target]:
    """Every real rule, from `make -pRrq` (phony flag, prerequisites) plus the Makefile text."""
    db = _make(["-pRrq", ":"], root).stdout
    section = db.split("# Files", 1)[-1]
    lines = (root / "Makefile").read_text(encoding="utf-8").splitlines()
    header_line: dict[str, int] = {}
    for i, text in enumerate(lines, 1):
        m = re.match(r"^([A-Za-z0-9_.%-]+):(?!=)", text)
        if m and m.group(1) not in header_line:
            header_line[m.group(1)] = i

    targets: dict[str, Target] = {}
    not_a_target = False
    current: Target | None = None
    for raw in section.splitlines():
        if raw.startswith("# Not a target"):
            not_a_target = True
            continue
        # A target/file header in `make -pRrq` output starts in column 0, is not a
        # comment or recipe line, and contains a colon. ANY such header closes the
        # preceding "# Not a target" scope, even one whose name our stricter rule
        # regex rejects -- notably the command-line goal `::`, which otherwise leaked
        # not_a_target onto the next real target and dropped it (e.g. `security`).
        if raw[:1] not in ("", " ", "\t", "#") and ":" in raw:
            m = re.match(r"^([^\s#:=][^:=]*?):(?!=)\s*(.*)$", raw)
            current = None
            if m and not not_a_target:
                name, prereq = m.group(1), m.group(2)
                if name in header_line and (not name.startswith(".") or name.startswith(".env.")):
                    current = targets.setdefault(name, Target(name, line=header_line[name]))
                    current.prereqs = [p for p in prereq.split("|")[0].split() if p]
            not_a_target = False
            continue
        if current is None:
            continue
        if "Phony target" in raw:
            current.phony = True
        if "recipe to execute" in raw:
            current.has_recipe = True

    # "Listed in help" is read from the real `make help` output, not re-derived from a regex copy.
    help_out = ANSI_RE.sub("", _make(["help"], root).stdout)
    listed = {ln.split()[0] for ln in help_out.splitlines() if ln.startswith("  ") and ln.split()}
    for t in targets.values():
        head = lines[t.line - 1]
        t.in_help = t.name in listed
        if "## " in head:
            t.help_text = head.split("## ", 1)[1].strip()
        for nxt in lines[t.line :]:
            if nxt.startswith("\t") or nxt.strip() == "":
                t.recipe.append(nxt)
            elif nxt.startswith("#"):
                continue
            else:
                break
    return targets


def dry_run(name: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return _make(["-n", name], root)


def recipe_paths(target: Target) -> set[str]:
    found: set[str] = set()
    for line in target.recipe:
        for m in PATH_RE.finditer(line):
            token = m.group(1).rstrip(".,;:)'\"")
            if "$" in token or "*" in token:
                continue
            found.add(token)
    return found


def missing_paths(target: Target, generated: list[str], root: Path = ROOT) -> list[str]:
    out = []
    for token in sorted(recipe_paths(target)):
        if any(re.search(g, token) for g in generated):
            continue
        if not (root / token).exists():
            out.append(token)
    return out


def load_classification(path: Path = CLASSIFICATION) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tracked_text_files(root: Path = ROOT) -> list[Path]:
    res = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=False
    )
    names = [n for n in res.stdout.decode("utf-8", "replace").split("\0") if n]
    return [root / n for n in names]


def doc_references(
    known: set[str], skip_prefixes: list[str], ignore: list[str], root: Path = ROOT
) -> list[tuple[str, int, str]]:
    """`make <target>` mentions in live docs/scripts that name a target that does not exist."""
    bad: list[tuple[str, int, str]] = []
    for path in tracked_text_files(root):
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(p) for p in skip_prefixes):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in DOC_REF_RE.finditer(line):
                word = m.group(1)
                if "-" not in word:
                    # Single words ("make sure", "make it") are prose, not targets.
                    continue
                if word in known or word in ignore:
                    continue
                bad.append((rel, lineno, word))
    return bad


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def build_report(targets: dict[str, Target], cls: dict, dry: dict[str, int], refs: list) -> str:
    entries = cls["targets"]
    names = sorted(targets, key=lambda n: (targets[n].line or 10**6, n))
    out: list[str] = []
    w = out.append
    w("# Makefile target audit (BITB-220)")
    w("")
    w(
        "> Generated by `scripts/audit_make_targets.py --write` from the Makefile and "
        "`scripts/make_target_audit.json`. Do not edit by hand; "
        "`make test-makefile` fails when this file is stale."
    )
    w("")
    w("## How to reproduce")
    w("")
    w("```bash")
    w("make test-makefile                                  # unit tests (fake az/docker/kubectl/terraform/gradle) + freshness check")
    w("python3 scripts/audit_make_targets.py --check        # invariants + this report is current")
    w("python3 scripts/audit_make_targets.py --list         # raw inventory from `make -pRrq`")
    w("python3 scripts/audit_make_targets.py --write        # regenerate this file")
    w("```")
    w("")
    w(
        "Every target is dry-run with `make -n` (no recipe executes). *Executed* says how the "
        "recipe itself was exercised: **real** = run for real during the audit on a machine with "
        "the shared venv; **mocked** = run by `scripts/test_make_targets.py` in a sandbox whose "
        "`az`, `docker`, `kubectl`, `terraform`, `curl`, `gradlew`, `pip` and `detect-secrets` are "
        "recording fakes; **static** = dry-run only, with the reason it could not be executed."
    )
    w("")
    total = len(targets)
    counts = {e: sum(1 for n in targets if entries[n]["execution"] == e) for e in EXECUTION}
    phony = sum(1 for t in targets.values() if t.phony)
    helped = sum(1 for t in targets.values() if t.in_help)
    w("## Summary")
    w("")
    w(f"- Targets: **{total}** ({phony} phony, {total - phony} file rules)")
    w(f"- Listed by `make help`: **{helped}**; hidden on purpose: {total - helped}")
    w(f"- Dry-run clean (`make -n`): **{sum(1 for r in dry.values() if r == 0)}/{total}**")
    w(
        f"- Executed: real **{counts['real']}**, mocked **{counts['mocked']}**, "
        f"static (blocked) **{counts['static']}**"
    )
    w("")
    by_safety: dict[str, int] = {}
    for n in targets:
        by_safety[entries[n]["safety"]] = by_safety.get(entries[n]["safety"], 0) + 1
    w("| Safety class | Targets |")
    w("|---|---|")
    for s in SAFETY_CLASSES:
        if s in by_safety:
            w(f"| `{s}` | {by_safety[s]} |")
    w("")
    w("## Defects found and fixed")
    w("")
    w("| ID | Severity | Targets | Defect | Regression test |")
    w("|---|---|---|---|---|")
    for d in cls["defects"]:
        if d["status"] != "fixed":
            continue
        tgt = ", ".join(f"`{t}`" for t in d["targets"])
        w(
            f"| {d['id']} | {d['severity']} | {tgt} | {_md_escape(d['summary'])} | "
            f"{_md_escape(d.get('test', '-'))} |"
        )
    w("")
    w("## Open findings (documented, not fixed here)")
    w("")
    w("| ID | Severity | Targets | Finding | Why not fixed |")
    w("|---|---|---|---|---|")
    for d in cls["defects"]:
        if d["status"] == "fixed":
            continue
        tgt = ", ".join(f"`{t}`" for t in d["targets"])
        w(
            f"| {d['id']} | {d['severity']} | {tgt} | {_md_escape(d['summary'])} | "
            f"{_md_escape(d.get('why', '-'))} |"
        )
    w("")
    w("## Target inventory")
    w("")
    w("| Target | Line | Phony | Help | Safety | Executed | Dry-run | Notes / blocked reason |")
    w("|---|---|---|---|---|---|---|---|")
    for n in names:
        t, e = targets[n], entries[n]
        note = e.get("blocked_reason") or e.get("note", "")
        if e["execution"] != "static" and e.get("note"):
            note = e["note"]
        elif e["execution"] == "static":
            note = e.get("blocked_reason", "")
            if e.get("note"):
                note = f"{note} {e['note']}".strip()
        w(
            f"| `{n}` | {t.line} | {'yes' if t.phony else 'no'} | {'yes' if t.in_help else 'no'} | "
            f"`{e['safety']}` | {e['execution']} | {'ok' if dry[n] == 0 else 'FAIL'} | "
            f"{_md_escape(note)} |"
        )
    w("")
    w("## Documentation references to missing targets")
    w("")
    if refs:
        for rel, lineno, word in refs:
            w(f"- `{rel}:{lineno}` -> `make {word}`")
    else:
        w(
            "None. Every hyphenated `make <target>` mentioned in tracked live docs, workflows and "
            "scripts exists (history/archives are excluded: "
            + ", ".join(f"`{p}`" for p in cls["doc_scan_skip"])
            + ")."
        )
    w("")
    return "\n".join(out).rstrip("\n") + "\n"


def check_invariants(targets: dict[str, Target], cls: dict) -> list[str]:
    problems: list[str] = []
    entries = cls["targets"]
    for n in sorted(set(targets) - set(entries)):
        problems.append(f"target {n!r} is not classified in {CLASSIFICATION.name}")
    for n in sorted(set(entries) - set(targets)):
        problems.append(f"{CLASSIFICATION.name} classifies {n!r}, which is not a Makefile target")
    for n, e in entries.items():
        if e.get("safety") not in SAFETY_CLASSES:
            problems.append(f"{n}: bad safety {e.get('safety')!r}")
        if e.get("execution") not in EXECUTION:
            problems.append(f"{n}: bad execution {e.get('execution')!r}")
        if e.get("execution") == "static" and not e.get("blocked_reason"):
            problems.append(f"{n}: static target needs a blocked_reason")
        if e.get("execution") == "mocked" and not e.get("tests"):
            problems.append(f"{n}: mocked target needs the covering tests listed")
        if e.get("execution") == "real" and not e.get("observed"):
            problems.append(f"{n}: real-run target needs an `observed` result")
    # Only the two env-file rules produce a file of their own name.
    for n, t in targets.items():
        if n in (".env.local", ".env.dev"):
            if t.phony:
                problems.append(f"{n} must not be phony (it creates the file)")
        elif not t.phony:
            problems.append(f"{n} is not in .PHONY")
        if t.has_recipe and not t.in_help and not entries.get(n, {}).get("hidden_ok"):
            problems.append(f"{n} has no `## description`; add one or mark hidden_ok")
    return problems


def run(args: argparse.Namespace) -> int:
    targets = load_targets()
    if args.list:
        for n in sorted(targets, key=lambda x: (targets[x].line, x)):
            t = targets[n]
            print(f"{t.line:5d}  {'P' if t.phony else '-'}{'H' if t.in_help else '-'}  {n}")
        print(f"# {len(targets)} targets", file=sys.stderr)
        return 0
    cls = load_classification()
    problems = check_invariants(targets, cls)
    dry = {n: dry_run(n).returncode for n in targets}
    for n, rc in dry.items():
        if rc != 0:
            problems.append(f"`make -n {n}` exited {rc}")
    generated = cls["generated_paths"]
    for n, t in targets.items():
        for p in missing_paths(t, generated):
            problems.append(f"{n}: recipe references {p}, which does not exist")
    refs = doc_references(set(targets), cls["doc_scan_skip"], cls["doc_ref_ignore"])
    for rel, lineno, word in refs:
        problems.append(f"{rel}:{lineno}: `make {word}` is not a target")
    report = build_report(targets, cls, dry, refs)
    if args.write:
        REPORT.write_text(report, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
    else:
        current = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
        if current != report:
            problems.append(
                f"{REPORT.relative_to(ROOT)} is stale; run "
                "`python3 scripts/audit_make_targets.py --write`"
            )
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"OK: {len(targets)} targets audited")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
