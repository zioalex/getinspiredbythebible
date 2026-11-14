#!/usr/bin/env python3
"""Validate ``docs/secrets-inventory.yaml`` and flag credentials about to expire (BITB-305).

The inventory records NAMES AND DATES ONLY, never a secret value, prefix or hash. Three checks:

1. Schema (always): top-level ``secrets:`` list; each entry has ``name``, ``kind``, ``used_by``
   (non-empty list of strings), ``expires`` (``YYYY-MM-DD`` | ``never`` | ``unknown``),
   ``rotation_doc`` (``path#anchor``) and ``owner``; optional ``description``. Unknown keys and
   duplicate names are errors.
2. Expiry (default mode, weekly): fails when an entry is expired or expires within
   ``WARN_DAYS`` (21) days. The boundary is inclusive: an entry whose expiry is exactly 21 days
   from today FAILS, 22 days passes. ``expires: unknown`` fails unless ``--allow-unknown``;
   ``never`` always passes.
3. ``--completeness`` (PR gate, no date logic so a PR never goes red because time passed):
   every ``secrets.NAME`` referenced under ``.github/workflows/*.yml`` must have an entry.
   ``GITHUB_TOKEN`` is excluded: GitHub mints it per run. Inventory entries of kind
   ``github-actions-secret`` that no workflow references any more are reported as warnings only.

Live GitHub PAT check (used by ``secrets-expiry-check.yml``): the workflow does the HTTP call and
passes only the *header value*, never the token, as ``--live-header NAME=<value>|none``. The
header ``github-authentication-token-expiration`` (``2026-12-01 12:00:00 UTC``) must match the
inventory date for NAME and be more than 21 days away; ``none`` (header absent: a token with no
expiry) requires the inventory to say ``never``. An inventory value of ``unknown`` is tolerated
only with ``--allow-unknown``.

Usage:

    python3 scripts/check_secrets_inventory.py --allow-unknown
    python3 scripts/check_secrets_inventory.py --completeness
    python3 scripts/check_secrets_inventory.py --allow-unknown \
        --live-header "RELEASE_PLEASE_TOKEN=2027-06-01 00:00:00 UTC"

Exit codes: 0 = ok, 1 = problems found, 2 = cannot run (unreadable file / bad arguments).
Offline unit tests: ``python -m pytest scripts/test_check_secrets_inventory.py -v``.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = ROOT / "docs" / "secrets-inventory.yaml"
DEFAULT_WORKFLOWS = ROOT / ".github" / "workflows"

WARN_DAYS = 21
# GitHub mints GITHUB_TOKEN for every run; it has no calendar expiry to track.
EXCLUDED_SECRETS = frozenset({"GITHUB_TOKEN"})
REQUIRED_FIELDS = ("name", "kind", "used_by", "expires", "rotation_doc", "owner")
OPTIONAL_FIELDS = ("description",)
KINDS = ("github-actions-secret", "terraform-variable")
SECRET_REF = re.compile(r"secrets\.([A-Z][A-Z0-9_]*)")
ROTATION_DOC = re.compile(r"^[^\s#]+#[^\s#]+$")
HEADER_DATE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})")


def load_inventory(path: Path) -> Any:
    """Parse the YAML file. Raises OSError / yaml.YAMLError for the caller to report."""
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def parse_date(raw: Any) -> date | None:
    """Strict ``YYYY-MM-DD`` string -> date, else None (PyYAML turns bare dates into dates)."""
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _validate_entry(entry: dict[str, Any], label: str) -> list[str]:
    """Field-level problems for one entry (name uniqueness is the caller's job)."""
    problems = [
        f"{label}: missing required field `{field}`"
        for field in REQUIRED_FIELDS
        if field not in entry or entry[field] in (None, "", [])
    ]
    allowed = set(REQUIRED_FIELDS) | set(OPTIONAL_FIELDS)
    problems += [f"{label}: unknown key `{field}`" for field in entry if field not in allowed]
    kind = entry.get("kind")
    if kind and kind not in KINDS:
        problems.append(f"{label}: kind {kind!r} not one of {', '.join(KINDS)}")
    used_by = entry.get("used_by")
    if used_by and (
        not isinstance(used_by, list) or not all(isinstance(u, str) and u for u in used_by)
    ):
        problems.append(f"{label}: `used_by` must be a list of non-empty strings")
    expires = entry.get("expires")
    if expires and expires not in ("never", "unknown") and parse_date(expires) is None:
        problems.append(f"{label}: expires {expires!r} must be YYYY-MM-DD, never or unknown")
    doc = entry.get("rotation_doc")
    if doc and not (isinstance(doc, str) and ROTATION_DOC.match(doc)):
        problems.append(f"{label}: rotation_doc {doc!r} must look like path#anchor")
    return problems


def validate_schema(data: Any) -> list[str]:
    """Schema problems; an empty list means the structure is valid."""
    if not isinstance(data, dict) or not isinstance(data.get("secrets"), list):
        return ["top level must be a mapping with a `secrets:` list"]
    problems: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(data["secrets"]):
        if not isinstance(entry, dict):
            problems.append(f"entry #{index}: must be a mapping")
            continue
        name = entry.get("name")
        label = str(name or f"entry #{index}")
        problems += _validate_entry(entry, label)
        if isinstance(name, str) and name:
            if name in seen:
                problems.append(f"{label}: duplicate name")
            seen.add(name)
        elif name not in (None, ""):
            problems.append(f"{label}: `name` must be a string")
    return problems


def _entries(data: Any) -> list[dict[str, Any]]:
    return [e for e in data["secrets"] if isinstance(e, dict)]


def check_expiry(data: Any, today: date, allow_unknown: bool = False) -> list[str]:
    """Problems for expired / expiring (<= WARN_DAYS) / unknown entries. Assumes valid schema."""
    problems: list[str] = []
    for entry in _entries(data):
        name, expires = entry["name"], entry["expires"]
        if expires == "never":
            continue
        if expires == "unknown":
            if not allow_unknown:
                problems.append(f"{name}: expires is unknown; record the real date")
            continue
        days_left = (parse_date(expires) - today).days  # type: ignore[operator]
        if days_left < 0:
            problems.append(f"{name}: EXPIRED on {expires} ({-days_left} days ago)")
        elif days_left <= WARN_DAYS:
            problems.append(f"{name}: expires {expires}, in {days_left} days (limit {WARN_DAYS})")
    return problems


def referenced_secrets(workflows_dir: Path) -> set[str]:
    """Every ``secrets.NAME`` used in the workflow files, minus the excluded names."""
    found: set[str] = set()
    for path in sorted(workflows_dir.glob("*.yml")):
        found.update(SECRET_REF.findall(path.read_text(encoding="utf-8")))
    return found - EXCLUDED_SECRETS


def check_completeness(data: Any, workflows_dir: Path) -> tuple[list[str], list[str]]:
    """(problems, warnings): missing entries fail; unreferenced workflow-secret entries warn."""
    used = referenced_secrets(workflows_dir)
    entries = _entries(data)
    names = {e["name"] for e in entries}
    problems = [
        f"{name}: used as secrets.{name} in .github/workflows but missing from the inventory"
        for name in sorted(used - names)
    ]
    warnings = [
        f"{e['name']}: inventory entry no longer referenced by any workflow"
        for e in entries
        if e.get("kind") == "github-actions-secret" and e["name"] not in used
    ]
    return problems, warnings


def check_live_header(
    data: Any, name: str, header: str | None, today: date, allow_unknown: bool = False
) -> list[str]:
    """Compare a live ``github-authentication-token-expiration`` value with the inventory.

    ``header`` is None / empty when GitHub sent no such header (token without expiry).
    """
    entry = next((e for e in _entries(data) if e.get("name") == name), None)
    if entry is None:
        return [f"{name}: not in the inventory"]
    recorded = entry["expires"]
    if not header or not header.strip():
        if recorded == "never" or (recorded == "unknown" and allow_unknown):
            return []
        return [f"{name}: GitHub reports no expiry but the inventory says {recorded}"]
    match = HEADER_DATE.match(header)
    live = parse_date(match.group(1)) if match else None
    if live is None:
        return [f"{name}: cannot parse the expiry header"]
    problems: list[str] = []
    days_left = (live - today).days
    if days_left < 0:
        problems.append(f"{name}: live token EXPIRED on {live.isoformat()}")
    elif days_left <= WARN_DAYS:
        problems.append(f"{name}: live token expires {live.isoformat()}, in {days_left} days")
    if recorded == "unknown":
        if not allow_unknown:
            problems.append(f"{name}: inventory expires is unknown; live date is {live}")
    elif recorded == "never" or parse_date(recorded) != live:
        problems.append(f"{name}: inventory says {recorded} but GitHub says {live.isoformat()}")
    return problems


def run(argv: Iterable[str] | None = None, today: date | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--workflows-dir", type=Path, default=DEFAULT_WORKFLOWS)
    parser.add_argument("--allow-unknown", action="store_true", help="tolerate expires: unknown")
    parser.add_argument(
        "--completeness",
        action="store_true",
        help="schema + every workflow secret has an entry; no date checks (PR gate)",
    )
    parser.add_argument(
        "--live-header",
        action="append",
        default=[],
        metavar="NAME=VALUE|none",
        help="compare a live token-expiration header value with the inventory",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    today = today or date.today()

    try:
        data = load_inventory(args.inventory)
    except (OSError, yaml.YAMLError) as error:
        print(f"cannot read {args.inventory}: {error}", file=sys.stderr)
        return 2

    problems = validate_schema(data)
    warnings: list[str] = []
    if not problems:
        if args.completeness:
            more, warnings = check_completeness(data, args.workflows_dir)
            problems += more
        elif args.live_header:
            for item in args.live_header:
                name, _, value = item.partition("=")
                value = "" if value.strip().lower() == "none" else value
                problems += check_live_header(data, name, value, today, args.allow_unknown)
        else:
            problems += check_expiry(data, today, args.allow_unknown)

    for warning in warnings:
        print(f"::warning::{warning}")
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(f"{len(problems)} problem(s) found.")
        return 1
    print("secrets inventory OK.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
