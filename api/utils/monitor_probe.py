"""
Synthetic-monitor probe bypass.

Production has Turnstile and rate limits enabled. A server-to-server probe
(GitHub Actions runner) cannot produce a valid Turnstile token, so we let
authorized probes opt-in via a shared secret header. The probe sends:

    X-Monitor-Probe-Secret: <value>

If the value matches `settings.monitor_probe_secret` (constant-time compare),
Turnstile and per-IP/session rate limits are skipped for the request. Other
guardrails (content filter, request validation, application logic) still
apply, so the probe exercises the same code path as a real user.

Bypass is fail-closed: if `settings.monitor_probe_secret` is unset/empty,
the header is ignored regardless of value.
"""

import hmac

from fastapi import Request

from config import settings

PROBE_HEADER = "X-Monitor-Probe-Secret"  # noqa: S105 - header name, not a secret


def is_monitor_probe(request: Request) -> bool:
    """Return True iff the request is an authorized synthetic monitor probe."""
    expected = settings.monitor_probe_secret
    if not expected:
        return False
    provided = request.headers.get(PROBE_HEADER)
    if not provided:
        return False
    return hmac.compare_digest(expected, provided)
