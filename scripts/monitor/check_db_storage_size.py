"""
Guard: PostgreSQL provisioned storage must equal the expected size.

BITB-232: Azure storage auto-grow doubled the disk (32 -> 64 GB) with every alert green,
because utilization % *drops* after a grow. Each grow is a permanent cost step (the disk
cannot shrink; see BITB-229). The only signal that catches the event itself is the
provisioned size, so this script lists every flexible server in the resource group via
`az postgres flexible-server list` and compares `storage.storageSizeGb` to the expected
size in GB.

Exit codes:
    0 — every server's provisioned storage equals the expected size
    1 — a mismatch, OR the state could not be verified (az failure, no servers, missing
        size / expected value) — an unverifiable guard must not look green

The failure detail is also written to the path passed via --detail-out so the caller
(CI workflow) can include it in the alert message.

Environment (or flags):
    RESOURCE_GROUP           — resource group holding the server (--resource-group)
    EXPECTED_DB_STORAGE_GB   — expected provisioned size in GB (--expected-gb)
"""

import argparse
import json
import os
import subprocess
import sys

FIX_HINT = (
    "Fix: investigate what is writing to the database (see the db-storage-pregrow alert); "
    "Azure cannot shrink the disk in place — see BITB-229 for the dump/restore shrink. "
    "After a deliberate size change, update EXPECTED_DB_STORAGE_GB in "
    ".github/workflows/prod-deploy-drift.yml."
)


def evaluate(servers: list[dict], expected_gb: int) -> list[str]:
    """Return a list of problems (empty == healthy). Pure function."""
    if not servers:
        return ["no PostgreSQL flexible servers found in the resource group"]
    problems: list[str] = []
    for server in servers:
        name = server.get("name")
        size = (server.get("storage") or {}).get("storageSizeGb")
        if isinstance(size, bool) or not isinstance(size, int | float):
            problems.append(f"server {name}: storageSizeGb missing or non-numeric ({size!r})")
        elif size != expected_gb:
            problems.append(
                f"server {name}: provisioned {size:g} GB, expected {expected_gb} GB — "
                "storage auto-grow fired (permanent cost step) or the disk was resized"
            )
    return problems


def _az(args: list[str]) -> object:
    try:
        result = subprocess.run(["az", *args], check=False, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"az could not be executed: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(f"az {' '.join(args[:2])} failed: {result.stderr.strip()[:300]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"az {' '.join(args[:2])} returned invalid JSON: {exc}") from exc


def fetch_servers(resource_group: str) -> list[dict]:
    servers = _az(["postgres", "flexible-server", "list", "-g", resource_group, "-o", "json"])
    if not isinstance(servers, list):
        raise RuntimeError("az postgres flexible-server list returned an unexpected payload")
    return servers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--resource-group", default=os.environ.get("RESOURCE_GROUP", ""))
    parser.add_argument("--expected-gb", default=os.environ.get("EXPECTED_DB_STORAGE_GB", ""))
    parser.add_argument("--detail-out", default=None)
    args = parser.parse_args(argv)

    expected_gb = 0
    try:
        if not args.resource_group:
            raise RuntimeError("no resource group given (--resource-group / RESOURCE_GROUP)")
        try:
            expected_gb = int(str(args.expected_gb).strip())
        except ValueError:
            raise RuntimeError(
                "expected size missing or not an integer (--expected-gb / EXPECTED_DB_STORAGE_GB)"
            ) from None
        if expected_gb <= 0:
            raise RuntimeError("expected size must be a positive number of GB")
        problems = evaluate(fetch_servers(args.resource_group), expected_gb)
    except RuntimeError as exc:
        problems = [f"could not verify PostgreSQL storage size: {exc}"]

    if not problems:
        print(f"OK: provisioned storage is {expected_gb} GB as expected")
        return 0

    detail = "\n".join([*problems, "", FIX_HINT])
    if args.detail_out:
        with open(args.detail_out, "w", encoding="utf-8") as fh:
            fh.write(detail + "\n")
    print(detail)
    return 1


if __name__ == "__main__":
    sys.exit(main())
