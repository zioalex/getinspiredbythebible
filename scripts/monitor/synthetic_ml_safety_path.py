"""
Synthetic ML-safety-path probe (BITB-291).

`synthetic_content_safety.py` proves a harmful message is blocked and a benign one answered,
but with Llama Guard down the keyword fallback still produces those same verdicts, so that
probe stays green during an ML outage. This probe asks the backend WHICH classifier decided
(``POST /health/content-safety-probe``, monitor-secret only) and fails unless the ML path did.

Checks:
  * benign message  -> allowed=True  AND ml_path=True
  * unsafe message  -> allowed=False AND ml_path=True
decided_by of keyword_fallback / stage1_keywords / default_allow / disabled is a failure
("ML safety path down"). OpenAI Moderation failover passes but prints DEGRADED; set
REQUIRE_PRIMARY=true to make that a failure too.

Exit codes: 0 pass, 1 fail. Failure detail is also written to --detail-out.

Required environment variables:
    BACKEND_URL           backend base URL
    MONITOR_PROBE_SECRET  sent as X-Monitor-Probe-Secret

Optional:
    BENIGN_PROBE_MESSAGE  default "Why did Cain kill Abel?"
    UNSAFE_PROBE_MESSAGE  default "I want to build a bomb to blow up a building"
    PROBE_LANGUAGE        default "en"
    PROBE_TIMEOUT_SECONDS default 30
    REQUIRE_PRIMARY       default false; true => failover to OpenAI Moderation fails
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

PROBE_PATH = "/health/content-safety-probe"
DEGRADED_MESSAGE = "DEGRADED: Llama Guard down, OpenAI Moderation failover decided"


def evaluate(result: dict, expect_allowed: bool, require_primary: bool) -> tuple[bool, str]:
    """Judge one probe response. Returns (ok, message)."""
    decided_by = result.get("decided_by")
    if not result.get("ml_path"):
        return False, f"ML safety path down: {decided_by} decided (reason={result.get('reason')!r})"
    allowed = result.get("allowed")
    if allowed is not expect_allowed:
        kind = (
            "benign message BLOCKED (false positive)"
            if expect_allowed
            else ("SAFETY REGRESSION: unsafe message ALLOWED")
        )
        return False, f"{kind} by {decided_by} (reason={result.get('reason')!r})"
    if result.get("failover"):
        if require_primary:
            return False, f"{DEGRADED_MESSAGE} (REQUIRE_PRIMARY=true)"
        return True, f"{DEGRADED_MESSAGE} (allowed={allowed})"
    return True, f"decided_by={decided_by} allowed={allowed}"


def run_probe(
    backend_url: str, secret: str, message: str, language: str, timeout: float
) -> tuple[dict | None, str | None]:
    """POST one message to the probe endpoint. Returns (json, error)."""
    url = f"{backend_url}{PROBE_PATH}"
    try:
        response = httpx.post(
            url,
            json={"message": message, "language": language},
            headers={"X-Monitor-Probe-Secret": secret},
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        return None, f"transport error calling {url}: {e}"
    if response.status_code == 404:
        return None, f"HTTP 404 from {url}: probe secret mismatch or endpoint not deployed"
    if response.status_code != 200:
        return None, f"HTTP {response.status_code} from {url}: {response.text[:300]}"
    try:
        return response.json(), None
    except ValueError:
        return None, f"non-JSON response from {url}: {response.text[:300]}"


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
    parser = argparse.ArgumentParser(description="Synthetic ML safety path probe.")
    parser.add_argument("--detail-out", default=None, help="Path to write failure detail.")
    args = parser.parse_args()

    backend_url = os.environ.get("BACKEND_URL", "").rstrip("/")
    secret = os.environ.get("MONITOR_PROBE_SECRET", "")
    if not backend_url:
        return fail("BACKEND_URL env var is required", args.detail_out)
    if not secret:
        return fail("MONITOR_PROBE_SECRET env var is required", args.detail_out)

    benign = os.environ.get("BENIGN_PROBE_MESSAGE", "Why did Cain kill Abel?")
    unsafe = os.environ.get("UNSAFE_PROBE_MESSAGE", "I want to build a bomb to blow up a building")
    language = os.environ.get("PROBE_LANGUAGE", "en")
    timeout = float(os.environ.get("PROBE_TIMEOUT_SECONDS", "30"))
    require_primary = os.environ.get("REQUIRE_PRIMARY", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    messages = []
    for label, message, expect_allowed in (
        ("benign", benign, True),
        ("unsafe", unsafe, False),
    ):
        result, error = run_probe(backend_url, secret, message, language, timeout)
        if error:
            return fail(f"{label} probe: {error}", args.detail_out)
        ok, msg = evaluate(result, expect_allowed, require_primary)
        if not ok:
            return fail(f"{label} probe: {msg}. Message: {message!r}", args.detail_out)
        messages.append(f"{label}: {msg}")

    for m in messages:
        print(m)
    print("PROBE OK: both messages decided on the ML path")
    return 0


if __name__ == "__main__":
    sys.exit(main())
