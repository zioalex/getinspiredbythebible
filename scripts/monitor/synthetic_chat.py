"""
Synthetic chat probe.

Sends a tiny chat request to /api/v1/chat/stream and validates the SSE
response. Catches the exact failure mode that caused the OpenRouter 401
incident — HTTP 200 with an in-band {"type": "error", ...} chunk that
naive 5xx alerts cannot see.

Exit codes:
    0 — probe passed (saw a 'completion' chunk, no errors)
    1 — probe failed (in-band error, missing chunks, timeout, or HTTP error)

The failure detail is also written to a file path passed via --detail-out
so the caller (CI workflow) can include it in alert messages.

Required environment variables:
    BACKEND_URL              — backend ACA URL, e.g. https://bible-app-backend.<...>.azurecontainerapps.io
    MONITOR_PROBE_SECRET     — shared secret matching settings.monitor_probe_secret
                               (sent as X-Monitor-Probe-Secret header to bypass Turnstile + rate limits)

Optional:
    PROBE_MESSAGE            — prompt to send (default: "hi")
    PROBE_TIMEOUT_SECONDS    — overall timeout (default: 30)
    PROBE_FIRST_CHUNK_SECONDS — fail if no content chunk arrives within this (default: 15)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid

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


def parse_sse_line(line: str) -> dict | str | None:
    """Parse one SSE 'data:' line. Returns the JSON object, the literal '[DONE]',
    or None for non-data lines (comments, blank lines, event:, id:, retry:)."""
    if not line.startswith("data:"):
        return None
    payload = line[5:].lstrip()
    if payload == "[DONE]":
        return "[DONE]"
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic chat probe.")
    parser.add_argument(
        "--detail-out",
        default=None,
        help="Path to write failure detail (for CI alert payload).",
    )
    args = parser.parse_args()

    backend_url = os.environ.get("BACKEND_URL", "").rstrip("/")
    probe_secret = os.environ.get("MONITOR_PROBE_SECRET", "")
    if not backend_url:
        return fail("BACKEND_URL env var is required", args.detail_out)
    if not probe_secret:
        return fail("MONITOR_PROBE_SECRET env var is required", args.detail_out)

    message = os.environ.get("PROBE_MESSAGE", "hi")
    overall_timeout = float(os.environ.get("PROBE_TIMEOUT_SECONDS", "30"))
    first_chunk_timeout = float(os.environ.get("PROBE_FIRST_CHUNK_SECONDS", "15"))

    url = f"{backend_url}/api/v1/chat/stream"
    session_id = f"monitor-probe-{uuid.uuid4().hex[:12]}"
    body = {
        "message": message,
        "conversation_history": [],
        "include_search": False,
        "session_id": session_id,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Monitor-Probe-Secret": probe_secret,
    }

    started = time.monotonic()
    saw_content = False
    saw_completion = False
    first_chunk_at: float | None = None
    last_chunk: dict | None = None

    try:
        with httpx.Client(timeout=httpx.Timeout(overall_timeout, read=overall_timeout)) as client:
            with client.stream("POST", url, json=body, headers=headers) as response:
                if response.status_code != 200:
                    text = response.read().decode("utf-8", errors="replace")[:500]
                    return fail(
                        f"HTTP {response.status_code} from {url}: {text}",
                        args.detail_out,
                    )

                for raw_line in response.iter_lines():
                    if time.monotonic() - started > overall_timeout:
                        return fail(
                            f"overall timeout {overall_timeout}s exceeded "
                            f"(saw_content={saw_content} last={last_chunk!r})",
                            args.detail_out,
                        )
                    if (
                        not saw_content
                        and time.monotonic() - started > first_chunk_timeout
                    ):
                        return fail(
                            f"no content chunk within {first_chunk_timeout}s "
                            f"(last={last_chunk!r})",
                            args.detail_out,
                        )

                    parsed = parse_sse_line(raw_line)
                    if parsed is None:
                        continue
                    if parsed == "[DONE]":
                        break
                    last_chunk = parsed
                    chunk_type = parsed.get("type")
                    if chunk_type == "error":
                        err = parsed.get("error", "<no error field>")
                        code = parsed.get("error_code")
                        return fail(
                            f"in-band SSE error: {err}"
                            + (f" (code={code})" if code else ""),
                            args.detail_out,
                        )
                    if chunk_type == "content":
                        if not saw_content:
                            first_chunk_at = time.monotonic() - started
                        saw_content = True
                    elif chunk_type == "completion":
                        saw_completion = True
    except httpx.TimeoutException as e:
        return fail(f"httpx timeout: {e}", args.detail_out)
    except httpx.HTTPError as e:
        return fail(f"httpx error: {e}", args.detail_out)

    if not saw_content:
        return fail("stream ended without any content chunk", args.detail_out)
    if not saw_completion:
        return fail(
            f"stream ended without completion chunk (last={last_chunk!r})",
            args.detail_out,
        )

    elapsed = time.monotonic() - started
    print(
        f"PROBE OK: first_chunk={first_chunk_at:.2f}s total={elapsed:.2f}s "
        f"session={session_id}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
