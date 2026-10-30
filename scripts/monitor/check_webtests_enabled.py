"""
Guard: the Application Insights availability web tests must be Enabled.

BITB-224: `azurerm_application_insights_standard_web_test.enabled` is Optional
with no default (=> false), and deployment/main.tf never set it, so both
synthetic availability tests (`<project>-availability`, `<project>-preflight`)
sat at `Enabled: false` in production. The `*-availability-failed` /
`*-preflight-failed` metric alerts only fire while the web test runs, so a
disabled test silently switches that monitoring layer off. Nothing watched the
property — this script does.

It lists every `Microsoft.Insights/webtests` resource in the resource group via
`az resource` (not `az monitor app-insights web-test`, which needs an extension)
and reports any test whose ARM `properties.Enabled` is not strictly `True`, plus
any expected test that does not exist.

Exit codes:
    0 — all web tests are enabled and every expected test exists
    1 — a test is disabled / missing, OR the state could not be verified
        (az failure) — an unverifiable guard must not look green

The failure detail is also written to the path passed via --detail-out so the
caller (CI workflow) can include it in the alert message.

Environment (or flags):
    RESOURCE_GROUP      — resource group holding the web tests (--resource-group)
    EXPECTED_WEBTESTS   — comma-separated web test names that must exist
                          (--expected)
"""

import argparse
import json
import os
import subprocess
import sys

FIX_HINT = (
    "Fix: terraform apply restores enabled=true (deployment/main.tf), or "
    "`az resource update --ids <id> --set properties.Enabled=true`."
)


def evaluate(tests: list[dict], expected: list[str]) -> list[str]:
    """Return a list of problems (empty == healthy). Pure function."""
    problems: list[str] = []
    by_name = {t.get("name"): t for t in tests}
    for name in expected:
        if name not in by_name:
            problems.append(f"{name}: web test not found")
    for test in tests:
        enabled = (test.get("properties") or {}).get("Enabled")
        if enabled is not True:
            problems.append(
                f"{test.get('name')}: Enabled={enabled} — "
                "synthetic availability monitoring is OFF"
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


def fetch_webtests(resource_group: str) -> list[dict]:
    """Fetch full ARM representations of every web test in the resource group."""
    ids = _az(
        [
            "resource",
            "list",
            "-g",
            resource_group,
            "--resource-type",
            "Microsoft.Insights/webtests",
            "--query",
            "[].id",
            "-o",
            "json",
        ]
    )
    if not isinstance(ids, list):
        raise RuntimeError("az resource list returned an unexpected payload")
    tests: list[dict] = []
    for resource_id in ids:
        test = _az(["resource", "show", "--ids", resource_id, "-o", "json"])
        if not isinstance(test, dict):
            raise RuntimeError(f"az resource show returned an unexpected payload for {resource_id}")
        tests.append(test)
    return tests


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--resource-group", default=os.environ.get("RESOURCE_GROUP", ""))
    parser.add_argument("--expected", default=os.environ.get("EXPECTED_WEBTESTS", ""))
    parser.add_argument("--detail-out", default=None)
    args = parser.parse_args(argv)

    expected = [n.strip() for n in args.expected.split(",") if n.strip()]

    try:
        if not args.resource_group:
            raise RuntimeError("no resource group given (--resource-group / RESOURCE_GROUP)")
        tests = fetch_webtests(args.resource_group)
        problems = evaluate(tests, expected)
    except RuntimeError as exc:
        problems = [f"could not verify web-test state: {exc}"]

    if not problems:
        print(f"OK: {len(expected)} expected web test(s) present and Enabled")
        return 0

    detail = "\n".join([*problems, "", FIX_HINT])
    if args.detail_out:
        with open(args.detail_out, "w", encoding="utf-8") as fh:
            fh.write(detail + "\n")
    print(detail)
    return 1


if __name__ == "__main__":
    sys.exit(main())
