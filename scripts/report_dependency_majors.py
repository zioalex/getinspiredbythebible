#!/usr/bin/env python3
"""Quarterly report of direct dependencies whose latest major version is ahead (BITB-304).

Dependabot ignores major bumps (.github/dependabot.yml), so this writes one markdown table
to ``$GITHUB_STEP_SUMMARY`` (stdout when unset) listing, for ``api/requirements.txt`` (PyPI)
and ``frontend/package.json`` (npm), every direct dependency whose latest published major is
greater than the pinned/declared major.

Report only: being behind never fails the run. A registry lookup that fails is listed in the
report as "lookup failed" rather than aborting. Standard library only. No GitHub Issues.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HTTP_TIMEOUT = 30

_REQ_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(?:==|>=|~=)\s*([^\s;#,]+)"
)
_MAJOR_RE = re.compile(r"(\d+)")


def parse_requirements(text: str) -> dict[str, str]:
    """Direct requirements pinned with ``==``, ``>=`` or ``~=``: ``{name: version}``."""
    pins: dict[str, str] = {}
    for line in text.splitlines():
        match = _REQ_RE.match(line)
        if match:
            pins[match.group(1)] = match.group(2)
    return pins


def parse_package_json(text: str) -> dict[str, str]:
    data = json.loads(text)
    deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        deps.update(data.get(key, {}))
    return deps


def major_of(version: str) -> int | None:
    """Leading numeric major of ``1.2.3``, ``^18.3.0``, ``~5``, ``>=2`` ...; None if no digits."""
    match = _MAJOR_RE.search(version)
    return int(match.group(1)) if match else None


def is_behind(current: str, latest: str) -> bool:
    cur, lat = major_of(current), major_of(latest)
    return cur is not None and lat is not None and lat > cur


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def latest_pypi(name: str) -> str:
    return _get_json(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json")["info"]["version"]


def latest_npm(name: str) -> str:
    # Scoped names keep the "@" and encode only the slash.
    return _get_json(f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}/latest")[
        "version"
    ]


def build_rows(deps: dict[str, str], fetch_latest) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return ``(behind_rows, failed_names)``; rows are ``(name, current, latest)``."""
    rows: list[tuple[str, str, str]] = []
    failed: list[str] = []
    for name, current in sorted(deps.items()):
        try:
            latest = fetch_latest(name)
        except Exception:  # noqa: BLE001 - one bad registry reply must not abort the report
            failed.append(name)
            continue
        if is_behind(current, latest):
            rows.append((name, current, latest))
    return rows, failed


def render_section(title: str, rows, failed: list[str]) -> str:
    lines = [f"### {title}", ""]
    if rows:
        lines += ["| Package | Current | Latest |", "| --- | --- | --- |"]
        lines += [f"| `{n}` | {c} | {latest} |" for n, c, latest in rows]
    else:
        lines.append("No direct dependency is behind by a major version.")
    if failed:
        lines += ["", "Lookup failed (not checked): " + ", ".join(f"`{n}`" for n in failed)]
    return "\n".join(lines) + "\n"


def main(root: Path = REPO_ROOT) -> int:
    py_deps = parse_requirements((root / "api" / "requirements.txt").read_text(encoding="utf-8"))
    js_deps = parse_package_json((root / "frontend" / "package.json").read_text(encoding="utf-8"))
    py_rows, py_failed = build_rows(py_deps, latest_pypi)
    js_rows, js_failed = build_rows(js_deps, latest_npm)
    report = "## Dependency major-version report\n\n"
    report += render_section("Python (api/requirements.txt)", py_rows, py_failed) + "\n"
    report += render_section("npm (frontend/package.json)", js_rows, js_failed)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report)
    else:
        print(report)
    return 0  # report only: being behind never fails the run


if __name__ == "__main__":
    sys.exit(main())
