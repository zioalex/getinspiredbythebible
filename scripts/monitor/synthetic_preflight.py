"""
Cross-origin (browser-shaped) smoke probe for the chat endpoint.

Every other synthetic probe sends the API the *non-browser* way — a direct
httpx/curl request with no Origin and no CORS preflight — so a browser-only
outage stays invisible. That is exactly what happened in the 2026-07-05
`_IncludedRouter` incident: `OPTIONS /api/v1/chat/stream` (the browser's CORS
preflight) returned HTTP 500 under the instrumented production backend, while
direct GET/POST returned 200, so nothing alerted. See BITB-064.

This probe reproduces the actual browser request sequence against the
**instrumented production** backend, in two steps:

1. CORS preflight — `OPTIONS /api/v1/chat/stream` with the same Origin +
   Access-Control-Request-* headers a browser sends. Asserts a 2xx/204 and that
   the response echoes `Access-Control-Allow-Origin` and advertises
   `Access-Control-Allow-Methods`. This is the direct, telemetry-independent
   catch for the incident class.

2. Cross-origin POST — `POST /api/v1/chat/stream` with the `Origin` header set
   (so the response CORS headers are exercised on the real request) plus the
   `X-Monitor-Probe-Secret` bypass (to pass Turnstile + rate limits
   deterministically). Asserts a streamed `content` + `completion` SSE chunk
   arrives and that `Access-Control-Allow-Origin` is present on the response.

Note: this bypasses Turnstile *verification* by design so the probe is
deterministic. The full browser journey (real widget, real streaming rendered
in Chromium) is the open part of BITB-064.

Exit codes:
    0 — probe passed (preflight OK + streamed answer with CORS headers)
    1 — probe failed (preflight non-2xx / missing CORS headers, HTTP error,
        missing SSE chunks, in-band error, or timeout)

The failure detail is also written to the path passed via --detail-out so the
caller (CI workflow) can include it in the alert message.

Required environment variables:
    BACKEND_URL              — backend ACA URL, e.g. https://bible-app-backend.<...>.azurecontainerapps.io
    MONITOR_PROBE_SECRET     — shared secret matching settings.monitor_probe_secret
                               (sent as X-Monitor-Probe-Secret to bypass Turnstile + rate limits)

Optional:
    PROBE_ORIGIN             — Origin header to send (default: https://voxquieta.org)
    PROBE_MESSAGE            — prompt to send on the POST (default: "What does John 3:16 say?")
    PROBE_TIMEOUT_SECONDS    — overall timeout for the streamed POST (default: 30)
    PROBE_FIRST_CHUNK_SECONDS — fail if no content chunk arrives within this (default: 20)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid

import httpx

CHAT_STREAM_PATH = "/api/v1/chat/stream"
# The exact headers a browser preflights the streaming chat request with — the
# `x-turnstile-token` custom header is what forces the preflight in the first place.
PREFLIGHT_REQUEST_HEADERS = "content-type,x-turnstile-token"


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


def check_preflight(
    client: httpx.Client, url: str, origin: str, detail_out: str | None
) -> int | None:
    """Send the browser CORS preflight. Returns an exit code on failure, or None
    if the preflight passed."""
    req_headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": PREFLIGHT_REQUEST_HEADERS,
    }
    try:
        resp = client.request("OPTIONS", url, headers=req_headers)
    except httpx.HTTPError as e:
        return fail(f"preflight OPTIONS {url} raised: {e}", detail_out)

    # A crashing/instrumentation-broken backend returns 500 here (the incident);
    # a healthy CORS layer returns 200/204.
    if resp.status_code >= 400:
        body = resp.text[:500]
        hint = (
            " A 5xx here is the browser-only failure signature of the "
            "_IncludedRouter/OTel incident (BITB-064)."
            if resp.status_code >= 500
            else ""
        )
        return fail(
            f"preflight OPTIONS {url} returned HTTP {resp.status_code} "
            f"(expected 2xx).{hint} body={body!r}",
            detail_out,
        )

    acao = resp.headers.get("access-control-allow-origin")
    acam = resp.headers.get("access-control-allow-methods")
    if acao not in (origin, "*"):
        return fail(
            f"preflight succeeded (HTTP {resp.status_code}) but "
            f"Access-Control-Allow-Origin={acao!r} does not allow Origin {origin!r} "
            f"— the browser would block the request as a CORS error",
            detail_out,
        )
    if not acam:
        return fail(
            f"preflight succeeded (HTTP {resp.status_code}, ACAO={acao!r}) but "
            f"Access-Control-Allow-Methods is missing — CORS response is malformed",
            detail_out,
        )
    print(
        f"PREFLIGHT OK: HTTP {resp.status_code} "
        f"ACAO={acao!r} ACAM={acam!r} for Origin {origin!r}"
    )
    return None


def check_cross_origin_stream(
    client: httpx.Client,
    url: str,
    origin: str,
    probe_secret: str,
    message: str,
    overall_timeout: float,
    first_chunk_timeout: float,
    detail_out: str | None,
) -> int:
    """Send the real cross-origin POST and validate the streamed SSE response.
    Returns a process exit code (0 pass, 1 fail)."""
    session_id = f"monitor-preflight-{uuid.uuid4().hex[:12]}"
    body = {
        "message": message,
        "conversation_history": [],
        "include_search": True,
        "session_id": session_id,
    }
    headers = {
        "Content-Type": "application/json",
        # Real browser sends Origin on the actual request too; setting it here
        # exercises the response CORS headers on the POST, not just the preflight.
        "Origin": origin,
        # Bypass Turnstile + rate limits so the probe is deterministic.
        "X-Monitor-Probe-Secret": probe_secret,
    }

    started = time.monotonic()
    saw_content = False
    saw_completion = False
    first_chunk_at: float | None = None
    last_chunk: dict | None = None

    try:
        with client.stream("POST", url, json=body, headers=headers) as response:
            if response.status_code != 200:
                text = response.read().decode("utf-8", errors="replace")[:500]
                return fail(
                    f"cross-origin POST {url} returned HTTP {response.status_code}: {text}",
                    detail_out,
                )
            acao = response.headers.get("access-control-allow-origin")
            if acao not in (origin, "*"):
                return fail(
                    f"cross-origin POST succeeded but Access-Control-Allow-Origin={acao!r} "
                    f"does not allow Origin {origin!r} — a browser would block reading the "
                    f"streamed response",
                    detail_out,
                )

            for raw_line in response.iter_lines():
                if time.monotonic() - started > overall_timeout:
                    return fail(
                        f"overall timeout {overall_timeout}s exceeded "
                        f"(saw_content={saw_content} last={last_chunk!r})",
                        detail_out,
                    )
                if not saw_content and time.monotonic() - started > first_chunk_timeout:
                    return fail(
                        f"no content chunk within {first_chunk_timeout}s (last={last_chunk!r})",
                        detail_out,
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
                        f"in-band SSE error: {err}" + (f" (code={code})" if code else ""),
                        detail_out,
                    )
                if chunk_type == "content":
                    if not saw_content:
                        first_chunk_at = time.monotonic() - started
                    saw_content = True
                elif chunk_type == "completion":
                    saw_completion = True
    except httpx.ReadTimeout:
        return fail(
            f"server unresponsive: no data received within {first_chunk_timeout}s "
            f"(saw_content={saw_content})",
            detail_out,
        )
    except httpx.TimeoutException as e:
        return fail(f"httpx timeout: {e}", detail_out)
    except httpx.HTTPError as e:
        return fail(f"httpx error: {e}", detail_out)

    if not saw_content:
        return fail("stream ended without any content chunk", detail_out)
    if not saw_completion:
        return fail(
            f"stream ended without completion chunk (last={last_chunk!r})",
            detail_out,
        )

    elapsed = time.monotonic() - started
    first = f"{first_chunk_at:.2f}s" if first_chunk_at is not None else "n/a"
    print(f"CROSS-ORIGIN STREAM OK: first_chunk={first} total={elapsed:.2f}s session={session_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-origin CORS-preflight smoke probe.")
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

    origin = os.environ.get("PROBE_ORIGIN", "https://voxquieta.org").rstrip("/")
    message = os.environ.get("PROBE_MESSAGE", "What does John 3:16 say?")
    overall_timeout = float(os.environ.get("PROBE_TIMEOUT_SECONDS", "30"))
    first_chunk_timeout = float(os.environ.get("PROBE_FIRST_CHUNK_SECONDS", "20"))

    url = f"{backend_url}{CHAT_STREAM_PATH}"

    with httpx.Client(
        timeout=httpx.Timeout(connect=10.0, read=first_chunk_timeout, write=10.0, pool=5.0)
    ) as client:
        preflight_result = check_preflight(client, url, origin, args.detail_out)
        if preflight_result is not None:
            return preflight_result
        return check_cross_origin_stream(
            client,
            url,
            origin,
            probe_secret,
            message,
            overall_timeout,
            first_chunk_timeout,
            args.detail_out,
        )


if __name__ == "__main__":
    sys.exit(main())
