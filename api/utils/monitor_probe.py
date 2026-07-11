"""
Synthetic-monitor probe bypass.

Production has Turnstile and rate limits enabled. A server-to-server probe
(GitHub Actions runner) cannot produce a valid Turnstile token, so we let
authorized probes opt-in via a shared secret header. The probe sends:

    X-Monitor-Probe-Secret: <value>

If the value matches `settings.monitor_probe_secret` OR the separate,
rotatable `settings.smoke_probe_secret` (constant-time compare), Turnstile and
per-IP/session rate limits are skipped for the request. Other guardrails
(content filter, request validation, application logic) still apply, so the
probe exercises the same code path as a real user.

The two secrets serve different callers: `monitor_probe_secret` is for the
server-to-server GitHub Actions probes; `smoke_probe_secret` (BITB-064) is for
the browser smoke test, which injects it into the ephemeral CI browser only —
never into the shipped bundle. Keeping them distinct makes the browser-facing
one independently revocable.

Bypass is fail-closed: if both secrets are unset/empty, the header is ignored
regardless of value.
"""

import hmac

from fastapi import Request

from config import settings

PROBE_HEADER = "X-Monitor-Probe-Secret"  # noqa: S105 - header name, not a secret


def is_monitor_probe(request: Request) -> bool:
    """Return True iff the request is an authorized synthetic monitor probe
    (server-to-server monitor secret) or the browser smoke test (smoke secret)."""
    provided = request.headers.get(PROBE_HEADER)
    if not provided:
        return False
    # Compare against every configured secret; constant-time per candidate.
    # `or ""` keeps the compare_digest call shape even when a secret is unset,
    # and an empty expected never matches a non-empty provided value.
    for expected in (settings.monitor_probe_secret, settings.smoke_probe_secret):
        if expected and hmac.compare_digest(expected, provided):
            return True
    return False
