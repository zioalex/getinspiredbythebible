"""
Local-only access restriction for sensitive endpoints.

Restricts access to endpoints that should only be accessible from
localhost or internal networks (e.g., health details, debug endpoints).
"""

import ipaddress
import logging

from fastapi import HTTPException, Request

from config import settings

logger = logging.getLogger(__name__)

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
    """
    Extract client IP from request, handling proxies.

    Checks X-Forwarded-For header first (for reverse proxy setups),
    then falls back to direct client host.
    """
    # Check X-Forwarded-For header (set by reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2
        # The first IP is the original client
        client_ip = forwarded_for.split(",")[0].strip()
        return client_ip

    # Check X-Real-IP header (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client
    if request.client:
        return request.client.host

    return ""


async def require_local_access(request: Request) -> None:
    """
    FastAPI dependency that restricts access to local IPs only.

    Raises 403 Forbidden if the request is from a non-local IP.

    In debug mode, allows requests without a client IP (e.g., test clients).

    Usage:
        @router.get("/debug", dependencies=[Depends(require_local_access)])
        async def debug_endpoint():
            ...
    """
    client_ip = get_client_ip(request)

    if not client_ip:
        # In debug mode, allow requests without client IP (test clients)
        if settings.debug:
            logger.debug("No client IP in debug mode, allowing access")
            return
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
