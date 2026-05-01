"""
Synthetic scripture-search probe.

GETs /api/v1/scripture/search?q=love&max_verses=2 and validates the response
has at least one verse, exercising the full stack: DB + embedding provider +
pgvector semantic search.

Exit codes:
    0 — probe passed
    1 — probe failed

Required environment variables:
    BACKEND_URL              — backend ACA URL
    MONITOR_PROBE_SECRET     — shared secret (same as synthetic_chat probe)

Optional:
    SEARCH_QUERY             — query to send (default: "love")
    SEARCH_TIMEOUT_SECONDS   — overall timeout (default: 20)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx


def fail(detail: str, detail_out: str | None) -> int:
    print(f"PROBE FAIL: {detail}", file=sys.stderr)
    if detail_out:
        try:
            with open(detail_out, "w", encoding="utf-8") as f:
                f.write(detail)
        except OSError as e:
            print(f"could not write detail to {detail_out}: {e}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic scripture-search probe.")
    parser.add_argument("--detail-out", default=None)
    args = parser.parse_args()

    backend_url = os.environ.get("BACKEND_URL", "").rstrip("/")
    probe_secret = os.environ.get("MONITOR_PROBE_SECRET", "")
    if not backend_url:
        return fail("BACKEND_URL env var is required", args.detail_out)
    if not probe_secret:
        return fail("MONITOR_PROBE_SECRET env var is required", args.detail_out)

    query = os.environ.get("SEARCH_QUERY", "love")
    timeout = float(os.environ.get("SEARCH_TIMEOUT_SECONDS", "20"))

    url = f"{backend_url}/api/v1/scripture/search"
    params = {"q": query, "max_verses": 2, "max_passages": 1}
    headers = {
        "X-Monitor-Probe-Secret": probe_secret,
        "Accept": "application/json",
    }

    started = time.monotonic()
    try:
        resp = httpx.get(
            url,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(connect=10.0, read=timeout, write=10.0, pool=5.0),
        )
    except httpx.TimeoutException as e:
        return fail(f"request timed out after {timeout}s: {e}", args.detail_out)
    except httpx.HTTPError as e:
        return fail(f"HTTP error: {e}", args.detail_out)

    elapsed = time.monotonic() - started

    if resp.status_code != 200:
        text = resp.text[:500]
        return fail(f"HTTP {resp.status_code} from {url}: {text}", args.detail_out)

    try:
        data = resp.json()
    except Exception as e:
        return fail(f"invalid JSON response: {e}\nbody: {resp.text[:300]}", args.detail_out)

    verses = data.get("verses", [])
    if not verses:
        return fail(
            f"search for '{query}' returned 0 verses — "
            f"embedding provider or pgvector may be down.\nResponse: {str(data)[:500]}",
            args.detail_out,
        )

    print(
        f"PROBE OK: search '{query}' returned {len(verses)} verse(s) in {elapsed:.2f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
