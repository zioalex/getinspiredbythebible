"""
Trusted client-IP resolution (BITB-297).

The single place in the API that reads ``X-Forwarded-For`` / ``CF-Connecting-IP``
(``X-Real-IP`` is deliberately ignored: nothing in our topology sets it).

Topology: client -> Cloudflare -> Azure Container Apps ingress (Envoy) -> uvicorn.
The Container Apps FQDN is also reachable directly, so every client-supplied
header can be forged. The chain ``XFF entries + [socket peer]`` is therefore
walked from the RIGHT, skipping hops inside a trusted-proxy network; the first
untrusted entry is the client. ``CF-Connecting-IP`` is used only as a fallback
when every hop is trusted and the last forwarded hop is a Cloudflare address.
"""

import ipaddress
from functools import lru_cache
from typing import Any

from fastapi import Request

from config import (
    CLOUDFLARE_CIDRS,
    DEFAULT_TRUSTED_PROXY_CIDRS,
    IPAddress,
    IPNetwork,
    parse_cidrs,
    settings,
)

__all__ = ["DEFAULT_TRUSTED_PROXY_CIDRS", "CLOUDFLARE_CIDRS", "resolve_client_ip"]

UNKNOWN = "unknown"
INVALID = "invalid"


@lru_cache(maxsize=8)
def _trusted_networks(value: str) -> tuple[IPNetwork, ...]:
    return parse_cidrs(value)


_CLOUDFLARE_NETWORKS = parse_cidrs(",".join(CLOUDFLARE_CIDRS))


def _parse_ip(raw: str) -> IPAddress | None:
    """Parse an IP, tolerating ``[v6]:port`` and ``v4:port``. IPv4-mapped IPv6 is unmapped."""
    text = raw.strip()
    candidates = [text]
    if text.startswith("[") and "]" in text:
        candidates.append(text[1 : text.index("]")])
    elif text.count(":") == 1:
        candidates.append(text.rsplit(":", 1)[0])
    for cand in candidates:
        try:
            ip = ipaddress.ip_address(cand)
        except ValueError:
            continue
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            return ip.ipv4_mapped
        return ip
    return None


def _in(ip: IPAddress, networks: tuple[IPNetwork, ...]) -> bool:
    return any(ip.version == n.version and ip in n for n in networks)


def _xff_entries(request: Request) -> list[str]:
    # A header can arrive as several lines; Starlette's ``.get`` returns only the first,
    # which would let a forged first line hide the proxy's own line. Join them all.
    raw = ",".join(request.headers.getlist("x-forwarded-for"))
    return [e.strip() for e in raw.split(",") if e.strip()]


def _peer(request: Request) -> str | None:
    return str(request.client.host) if request.client and request.client.host else None


def resolve_client_ip(request: Request) -> str:
    """Return the client IP, trusting only hops inside the trusted-proxy networks.

    Never returns a loopback/private address for a request that travelled through a
    Cloudflare hop: such a value can only be forged (Cloudflare does not proxy for
    private clients), so the Cloudflare hop itself is returned instead.
    """
    trusted = _trusted_networks(settings.trusted_proxy_cidrs)
    peer = _peer(request)
    if peer is None:
        # No socket peer (not possible over TCP): nothing vouches for the header.
        return UNKNOWN
    chain = _xff_entries(request) + [peer]

    cloudflare_hop: IPAddress | None = None  # nearest (right-most) Cloudflare hop
    for entry in reversed(chain):
        ip = _parse_ip(entry)
        if ip is None:
            # Unparseable: untrusted, never mistaken for a local address -- and never
            # allowed to collide with the UNKNOWN sentinel.
            return INVALID if entry.lower() == UNKNOWN else entry
        if not _in(ip, trusted):
            return str(ip)
        if cloudflare_hop is None and _in(ip, _CLOUDFLARE_NETWORKS):
            cloudflare_hop = ip

    # Every hop is trusted.
    if cloudflare_hop is None:
        # Purely internal chain (container health check, same-network caller).
        first = _parse_ip(chain[0])
        return str(first) if first is not None else chain[0]

    # The request came from a Cloudflare address and nothing to its left is a plausible
    # client. Accept CF-Connecting-IP only when the hop that handed the request to the
    # ingress is Cloudflare and the value is a non-proxy address; otherwise answer with
    # the Cloudflare hop (public, so never "local").
    last = _parse_ip(chain[-2]) if len(chain) > 1 else None
    if last is not None and _in(last, _CLOUDFLARE_NETWORKS):
        cf = _parse_ip(request.headers.get("CF-Connecting-IP", ""))
        if cf is not None and not _in(cf, trusted):
            return str(cf)
    return str(cloudflare_hop)


def was_forwarded(request: Request) -> bool:
    """True when the request carries a forwarded-for header, i.e. came through a proxy."""
    return bool(_xff_entries(request))


def describe_request_chain(request: Request) -> dict[str, Any]:
    """Diagnostic view of the chain as seen by this process (admin endpoint)."""
    return {
        "x_forwarded_for": _xff_entries(request),
        "peer": _peer(request),
        "cf_connecting_ip": request.headers.get("CF-Connecting-IP"),
        "resolved": resolve_client_ip(request),
    }
