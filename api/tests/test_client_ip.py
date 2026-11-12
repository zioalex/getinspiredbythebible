"""Tests for the trusted-proxy client-IP resolver (BITB-297)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.datastructures import Headers

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CLOUDFLARE_CIDRS, DEFAULT_TRUSTED_PROXY_CIDRS, Settings, settings
from utils.client_ip import UNKNOWN, describe_request_chain, resolve_client_ip
from utils.local_only import is_local_ip, require_local_access
from utils.security import require_rate_limit

CF4 = "172.64.0.1"  # inside 172.64.0.0/13 (Cloudflare)
CF6 = "2606:4700::1"  # inside 2606:4700::/32 (Cloudflare)
INGRESS = "10.0.0.5"  # Container Apps ingress hop (private)
CLIENT = "203.0.113.9"
CLIENT6 = "2001:db8::1"


def _req(xff=None, peer=INGRESS, cf=None, real_ip=None):
    """Request double with REAL Starlette headers (case-insensitive, repeatable lines).

    ``xff`` may be a string (one header line) or a list of strings (several lines).
    """
    raw: list[tuple[bytes, bytes]] = []
    for line in [xff] if isinstance(xff, str) else (xff or []):
        raw.append((b"x-forwarded-for", line.encode()))
    if cf is not None:
        raw.append((b"cf-connecting-ip", cf.encode()))
    if real_ip is not None:
        raw.append((b"x-real-ip", real_ip.encode()))
    request = MagicMock()
    request.headers = Headers(raw=raw)
    if peer is None:
        request.client = None
    else:
        request.client = MagicMock()
        request.client.host = peer
    return request


@pytest.mark.parametrize(
    "xff,peer,cf,expected",
    [
        # Via Cloudflare, forged left entry
        (f"127.0.0.1, {CLIENT}, {CF4}", INGRESS, None, CLIENT),
        # Direct to Container Apps, forged left entry
        (f"127.0.0.1, {CLIENT}", INGRESS, None, CLIENT),
        # Ingress overwrote the header; only the Cloudflare hop remains
        (CF4, INGRESS, CLIENT, CLIENT),
        # Forged private entries only to the left of the real client
        (f"10.1.1.1, 192.168.0.1, {CLIENT}", INGRESS, None, CLIENT),
        # No header, local peer
        (None, "127.0.0.1", None, "127.0.0.1"),
        # No header, public peer
        (None, CLIENT, None, CLIENT),
        # Garbage entry is untrusted and returned as-is
        ("not-an-ip", INGRESS, None, "not-an-ip"),
        # IPv6 client behind a Cloudflare IPv6 hop
        (f"{CLIENT6}, {CF6}", INGRESS, None, CLIENT6),
        # CF-Connecting-IP forged on a direct hit is ignored
        (CLIENT, INGRESS, "127.0.0.1", CLIENT),
        # CF-Connecting-IP ignored when the forwarded hop is private, not Cloudflare
        ("10.9.9.9", INGRESS, CLIENT, "10.9.9.9"),
        # CF-Connecting-IP garbage with a Cloudflare hop: fall back to left-most entry
        (CF4, INGRESS, "not-an-ip", CF4),
        # IPv4-mapped IPv6 client is unmapped
        (f"::ffff:{CLIENT}", INGRESS, None, CLIENT),
        # Port suffix and bracketed IPv6 are stripped
        (f"{CLIENT}:51234", INGRESS, None, CLIENT),
        (f"[{CLIENT6}]:443", INGRESS, None, CLIENT6),
        # Whitespace / empty entries tolerated
        (f" , {CLIENT} ,, {CF4} ", INGRESS, None, CLIENT),
        # Forged loopback IPv6 / mapped loopback from a public peer
        ("::1", CLIENT, None, CLIENT),
        ("::ffff:127.0.0.1", CLIENT, None, CLIENT),
    ],
)
def test_resolve_client_ip_table(xff, peer, cf, expected):
    assert resolve_client_ip(_req(xff=xff, peer=peer, cf=cf)) == expected


@pytest.mark.parametrize(
    "xff,cf,expected",
    [
        # Sender is a Cloudflare address (e.g. a Worker hitting the Container Apps FQDN):
        # forged loopback/private entries to its left must never be returned.
        (f"127.0.0.1, {CF4}", None, CF4),
        (f"10.0.0.1, 192.168.1.1, {CF4}", None, CF4),
        (f"::1, {CF6}", None, CF6),
        # ... nor a forged CF-Connecting-IP naming a loopback/private/proxy address.
        (CF4, "127.0.0.1", CF4),
        (CF4, "10.0.0.1", CF4),
        (CF4, "172.64.0.9", CF4),
        # A literal "unknown" entry must not collide with the UNKNOWN sentinel.
        (f"unknown, {CF4}", None, "invalid"),
        (f"UNKNOWN, {CF4}", None, "invalid"),
    ],
)
def test_forgery_from_a_cloudflare_sender_never_resolves_local(xff, cf, expected):
    resolved = resolve_client_ip(_req(xff=xff, cf=cf))
    assert resolved == expected
    assert not is_local_ip(resolved)
    assert resolved != UNKNOWN


def test_duplicate_forwarded_header_lines_are_joined():
    """A forged first header line must not hide the line the proxy added."""
    assert resolve_client_ip(_req(xff=["127.0.0.1", CLIENT])) == CLIENT
    # Order as received: the LAST line is nearest the server, so it wins.
    assert resolve_client_ip(_req(xff=["127.0.0.1", f"10.0.0.1, {CLIENT}"])) == CLIENT


def test_header_name_is_case_insensitive():
    request = _req()
    request.headers = Headers(raw=[(b"X-FORWARDED-FOR".lower(), f"127.0.0.1, {CLIENT}".encode())])
    assert resolve_client_ip(request) == CLIENT


def test_no_socket_peer_ignores_the_header():
    """Without a peer nothing vouches for the header, so it is not believed."""
    assert resolve_client_ip(_req(xff="127.0.0.1", peer=None)) == UNKNOWN


@pytest.mark.parametrize("value", ["", "   ", " , "])
def test_empty_trusted_cidrs_rejected(value):
    with pytest.raises(ValidationError):
        Settings(trusted_proxy_cidrs=value)


@pytest.mark.parametrize("value", ["0.0.0.0/0", "::/0", "64.0.0.0/2", "10.0.0.0/8,0.0.0.0/1"])
def test_overbroad_trusted_cidrs_rejected(value):
    with pytest.raises(ValidationError):
        Settings(trusted_proxy_cidrs=value)


def test_default_trusted_cidrs_pass_validation():
    assert Settings(trusted_proxy_cidrs=DEFAULT_TRUSTED_PROXY_CIDRS).trusted_proxy_cidrs


def test_empty_chain_is_unknown():
    assert resolve_client_ip(_req(xff=None, peer=None)) == "unknown"


def test_x_real_ip_is_ignored():
    assert resolve_client_ip(_req(peer=CLIENT, real_ip="127.0.0.1")) == CLIENT


def test_garbage_entry_is_not_local():
    from utils.local_only import is_local_ip

    assert not is_local_ip(resolve_client_ip(_req(xff="localhost")))


def test_custom_trusted_cidrs_override():
    # Only 203.0.113.0/24 is trusted: the proxy hop 203.0.113.9 is skipped, so the
    # real client is the next entry; the default-private ingress is now untrusted.
    with patch.object(settings, "trusted_proxy_cidrs", "203.0.113.0/24"):
        assert resolve_client_ip(_req(xff="198.51.100.7, 203.0.113.9", peer="203.0.113.10")) == (
            "198.51.100.7"
        )
        # A private peer is no longer trusted under the override
        assert resolve_client_ip(_req(xff="198.51.100.7", peer=INGRESS)) == INGRESS


def test_cloudflareness_decided_by_constant_not_setting():
    # Operator trusts only the private ingress; the Cloudflare hop is then the client
    # (untrusted), so CF-Connecting-IP is not consulted.
    with patch.object(settings, "trusted_proxy_cidrs", "10.0.0.0/8"):
        assert resolve_client_ip(_req(xff=CF4, cf=CLIENT)) == CF4
    # Trusting everything incl. Cloudflare still uses the constant for the fallback.
    with patch.object(settings, "trusted_proxy_cidrs", "10.0.0.0/8,172.64.0.0/13"):
        assert resolve_client_ip(_req(xff=CF4, cf=CLIENT)) == CLIENT


def test_default_setting_includes_cloudflare_ranges():
    for cidr in CLOUDFLARE_CIDRS:
        assert cidr in DEFAULT_TRUSTED_PROXY_CIDRS.split(",")


def test_invalid_cidr_fails_settings_validation():
    with pytest.raises(ValidationError):
        Settings(trusted_proxy_cidrs="10.0.0.0/8,not-a-cidr")


def test_valid_cidr_override_accepted():
    assert Settings(trusted_proxy_cidrs="10.0.0.0/8").trusted_proxy_cidrs == "10.0.0.0/8"


def test_describe_request_chain_payload():
    desc = describe_request_chain(_req(xff=f"{CLIENT}, {CF4}", cf=CLIENT))
    assert desc == {
        "x_forwarded_for": [CLIENT, CF4],
        "peer": INGRESS,
        "cf_connecting_ip": CLIENT,
        "resolved": CLIENT,
    }


# ---------------------------------------------------------------------------
# require_local_access through a real FastAPI app
# ---------------------------------------------------------------------------


def _local_app() -> FastAPI:
    local_app = FastAPI()

    @local_app.get("/local", dependencies=[Depends(require_local_access)])
    async def local():
        return {"ok": True}

    return local_app


@pytest.mark.parametrize("forged", ["127.0.0.1", "testclient", "10.0.0.1", "::1", "localhost"])
def test_local_only_rejects_forged_xff_from_public_peer(forged):
    client = TestClient(_local_app(), client=("203.0.113.9", 5555))
    resp = client.get("/local", headers={"X-Forwarded-For": forged})
    assert resp.status_code == 403


def test_local_only_rejects_forged_real_ip_from_public_peer():
    client = TestClient(_local_app(), client=("203.0.113.9", 5555))
    assert client.get("/local", headers={"X-Real-IP": "127.0.0.1"}).status_code == 403


@pytest.mark.parametrize("peer", ["127.0.0.1", "10.0.0.5", "203.0.113.9"])
@pytest.mark.parametrize(
    "xff", ["127.0.0.1", "10.0.0.1", "127.0.0.1, 10.0.0.1", f"127.0.0.1, {CF4}", "::1"]
)
def test_local_only_rejects_any_proxied_request(peer, xff):
    """Even from a private (ingress) peer, a forwarded request is never local."""
    client = TestClient(_local_app(), client=(peer, 5555))
    assert client.get("/local", headers={"X-Forwarded-For": xff}).status_code == 403


def test_local_only_allows_loopback_peer_without_header():
    client = TestClient(_local_app(), client=("127.0.0.1", 50000))
    assert client.get("/local").status_code == 200


def test_local_only_rejects_default_testclient_peer():
    # Starlette's default peer is the literal string "testclient": no longer special.
    assert TestClient(_local_app()).get("/local").status_code == 403


def test_local_only_debug_allows_undeterminable_ip():
    request = _req(xff=None, peer=None)
    import asyncio

    with patch.object(settings, "debug", True):
        asyncio.run(require_local_access(request))  # does not raise


def test_local_only_denies_undeterminable_ip_outside_debug():
    import asyncio

    from fastapi import HTTPException

    with patch.object(settings, "debug", False), pytest.raises(HTTPException) as exc:
        asyncio.run(require_local_access(_req(xff=None, peer=None)))
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Rate limiting keys on the resolved IP, not the forgeable left-most entry
# ---------------------------------------------------------------------------


def _rate_app() -> FastAPI:
    rate_app = FastAPI()

    @rate_app.get("/limited", dependencies=[Depends(require_rate_limit)])
    async def limited():
        return {"ok": True}

    return rate_app


def test_rate_limit_key_ignores_rotating_left_most_xff():
    limiter = AsyncMock()
    limiter.check_rate_limit = AsyncMock(return_value=(True, None))
    client = TestClient(_rate_app(), client=(INGRESS, 5555))
    with (
        patch.object(settings, "rate_limit_enabled", True),
        patch.object(settings, "monitor_probe_secret", None),
        patch("utils.security.get_rate_limiter", return_value=limiter),
    ):
        for i in range(25):
            resp = client.get(
                "/limited", headers={"X-Forwarded-For": f"198.51.100.{i}, {CLIENT}, {CF4}"}
            )
            assert resp.status_code == 200
    keys = {call.args[0] for call in limiter.check_rate_limit.await_args_list}
    assert keys == {CLIENT}
    assert limiter.check_rate_limit.await_count == 25


def test_rate_limit_rotating_xff_hits_per_ip_limit_on_21st_request():
    from utils.rate_limiter import RateLimiter

    limiter = RateLimiter(requests_per_minute=20, backend="memory")
    client = TestClient(_rate_app(), client=(INGRESS, 5555))
    with (
        patch.object(settings, "rate_limit_enabled", True),
        patch.object(settings, "monitor_probe_secret", None),
        patch("utils.security.get_rate_limiter", return_value=limiter),
    ):
        codes = [
            client.get(
                "/limited", headers={"X-Forwarded-For": f"198.51.100.{i}, {CLIENT}, {CF4}"}
            ).status_code
            for i in range(21)
        ]
    assert codes[:20] == [200] * 20
    assert codes[20] == 429
