"""
Local-only access restriction for sensitive endpoints.

Restricts access to endpoints that should only be accessible from
localhost or internal networks (e.g., health details, debug endpoints).
"""

import ipaddress

from fastapi import HTTPException, Request

from config import settings
from utils.client_ip import UNKNOWN, resolve_client_ip, was_forwarded
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Local/internal IP ranges
LOCAL_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),  # Private class A
    ipaddress.ip_network("172.16.0.0/12"),  # Private class B
    ipaddress.ip_network("192.168.0.0/16"),  # Private class C
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def is_local_ip(ip_str: str) -> bool:
    """Check if an IP address is local/internal."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in LOCAL_NETWORKS)
    except ValueError:
        # Invalid IP address format
        logger.warning(f"Invalid IP address format: {ip_str}")
        return False


def get_client_ip(request: Request) -> str:
    """Client IP resolved through the trusted-proxy chain (see utils/client_ip.py)."""
    return resolve_client_ip(request)


async def require_local_access(request: Request) -> None:
    """
    FastAPI dependency that restricts access to local IPs only.

    Raises 403 Forbidden if the request is from a non-local IP.

    Allows:
    - Local/internal IP addresses
    - Undeterminable IPs in debug mode

    Usage:
        @router.get("/debug", dependencies=[Depends(require_local_access)])
        async def debug_endpoint():
            ...
    """
    # A request relayed by any proxy is not local, whatever the header claims: local
    # callers (container health check, same-host curl) connect directly (BITB-297).
    if was_forwarded(request):
        logger.warning("Proxied request to a local-only endpoint, denying access")
        raise HTTPException(
            status_code=403,
            detail="Access denied: this endpoint is only accessible from local network",
        )

    client_ip = resolve_client_ip(request)

    # In debug mode, allow an undeterminable IP (e.g., from test frameworks)
    if settings.debug and client_ip == UNKNOWN:
        logger.debug("No client IP in debug mode, allowing access")
        return

    if client_ip == UNKNOWN:
        logger.warning("Could not determine client IP, denying access")
        raise HTTPException(
            status_code=403,
            detail="Access denied: could not determine client IP",
        )

    if not is_local_ip(client_ip):
        logger.warning(f"Non-local access attempt to restricted endpoint from {client_ip}")
        raise HTTPException(
            status_code=403,
            detail="Access denied: this endpoint is only accessible from local network",
        )
