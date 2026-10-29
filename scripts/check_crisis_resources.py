#!/usr/bin/env python3
"""Staleness check for the crisis-resources registry (BITB-251).

Fails (exit 1) when, in ``api/utils/crisis_resources.json``:

* any emergency or crisis-line entry has ``verified_on`` null / unparseable, or older than
  ``--max-age-days`` (default 180), or dated in the future;
* any ``source_url`` does not answer with a 2xx/3xx status (HEAD first, falling back to GET).

It is NOT a PR gate: it runs weekly from ``.github/workflows/crisis-resources-staleness.yml``
(and on demand) so PRs never go red just because time passed. Re-verification procedure:
``docs/HOW-TO-VERIFY-CRISIS-RESOURCES.md``.

Usage (stdlib only, Python 3.9+):

    python3 scripts/check_crisis_resources.py                 # full check
    python3 scripts/check_crisis_resources.py --skip-urls     # dates only, no network
    python3 scripts/check_crisis_resources.py --max-age-days 90 --timeout 20
    python3 scripts/check_crisis_resources.py --registry path/to/crisis_resources.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Callable

DEFAULT_REGISTRY = (
    Path(__file__).resolve().parent.parent / "api" / "utils" / "crisis_resources.json"
)
DEFAULT_MAX_AGE_DAYS = 180
DEFAULT_TIMEOUT = 15.0
USER_AGENT = "VoxQuieta-crisis-resources-check/1.0 (+https://voxquieta.org)"

Entry = tuple[str, dict[str, Any]]
# (url, method, timeout) -> HTTP status code; raises on network failure.
Fetcher = Callable[[str, str, float], int]


def collect_entries(registry: dict[str, Any]) -> list[Entry]:
    """Every emergency entry and crisis line, labelled for messages."""
    entries: list[Entry] = []
    for country, entry in sorted(registry.get("emergency", {}).items()):
        entries.append((f"emergency[{country}]", entry))
    for country, lines in sorted(registry.get("lines", {}).items()):
        for line in lines:
            entries.append((f"lines[{country}][{line.get('id', '?')}]", line))
    return entries


def check_verification(
    entries: list[Entry], today: date, max_age_days: int = DEFAULT_MAX_AGE_DAYS
) -> list[str]:
    """Problems with verified_on / verified_by (null, malformed, future, too old)."""
    problems: list[str] = []
    for label, entry in entries:
        raw = entry.get("verified_on")
        if not raw:
            problems.append(f"{label}: never verified (verified_on is null)")
            continue
        try:
            verified = date.fromisoformat(raw)
        except (TypeError, ValueError):
            problems.append(f"{label}: verified_on {raw!r} is not an ISO date")
            continue
        age = (today - verified).days
        if age < 0:
            problems.append(f"{label}: verified_on {raw} is in the future")
        elif age > max_age_days:
            problems.append(f"{label}: verified {age} days ago (limit {max_age_days}): {raw}")
        if not entry.get("verified_by"):
            problems.append(f"{label}: verified_on is set but verified_by is empty")
    return problems


def http_status(url: str, method: str, timeout: float) -> int:
    """Real fetcher: status code of one request (HTTP errors return their code)."""
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)


def url_is_alive(url: str, timeout: float, fetch: Fetcher = http_status) -> tuple[bool, str]:
    """HEAD first; any HEAD failure (status >= 400 or network error) falls back to GET."""
    detail = ""
    for method in ("HEAD", "GET"):
        try:
            status = fetch(url, method, timeout)
        except Exception as error:  # noqa: BLE001 - report any network failure, then retry
            detail = f"{method} {type(error).__name__}: {error}"
            continue
        if 200 <= status < 400:
            return True, f"{method} {status}"
        detail = f"{method} {status}"
    return False, detail


def check_urls(
    entries: list[Entry], timeout: float = DEFAULT_TIMEOUT, fetch: Fetcher = http_status
) -> list[str]:
    """Problems for every source_url that does not return 2xx/3xx."""
    by_url: dict[str, list[str]] = {}
    for label, entry in entries:
        url = entry.get("source_url")
        if not url:
            by_url.setdefault("", []).append(label)
        else:
            by_url.setdefault(url, []).append(label)

    problems = [f"{label}: missing source_url" for label in by_url.pop("", [])]
    urls = sorted(by_url)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda u: url_is_alive(u, timeout, fetch), urls))
    for url, (alive, detail) in zip(urls, results):
        if not alive:
            labels = ", ".join(by_url[url])
            problems.append(f"{url} is unreachable ({detail}); used by {labels}")
    return problems


def run(
    registry_path: Path,
    today: date,
    max_age_days: int,
    timeout: float,
    skip_urls: bool,
    fetch: Fetcher = http_status,
) -> list[str]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = collect_entries(registry)
    problems = check_verification(entries, today, max_age_days)
    if not skip_urls:
        problems += check_urls(entries, timeout, fetch)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--skip-urls", action="store_true", help="check dates only (no network)")
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="override today")
    args = parser.parse_args(argv)

    problems = run(
        args.registry,
        args.today or date.today(),
        args.max_age_days,
        args.timeout,
        args.skip_urls,
    )
    if problems:
        print(f"Crisis resources check FAILED ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  - {problem}")
        print("See docs/HOW-TO-VERIFY-CRISIS-RESOURCES.md for the re-verification procedure.")
        return 1
    print("Crisis resources check passed: every entry is verified, recent, and reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
