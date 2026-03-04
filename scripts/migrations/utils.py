"""
Utility functions for database migrations.

Note: asyncpg does NOT support ssl/sslmode as URL query parameters
(unlike psycopg2). SSL settings must be passed as a separate `ssl`
parameter to asyncpg.connect(). This module provides a helper to
extract those parameters from the URL.

Inspired by: api/scripture/database.py -> get_async_database_url()
"""

import ssl
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def get_migration_connection_params(database_url: str) -> tuple[str, dict]:
    """
    Parse database URL and extract SSL parameters for asyncpg.

    asyncpg doesn't support ssl/sslmode as URL query parameters.
    This function extracts them and returns a clean URL plus connection kwargs.

    Inspired by: api/scripture/database.py -> get_async_database_url()

    Args:
        database_url: Database URL (may include ?ssl=require or ?sslmode=require)

    Returns:
        Tuple of (clean_url, connection_kwargs)

    Example:
        >>> url = "postgresql://user:pass@host/db?ssl=require"  # pragma: allowlist secret
        >>> clean_url, kwargs = get_migration_connection_params(url)
        >>> conn = await asyncpg.connect(clean_url, **kwargs)
    """
    url = database_url
    conn_kwargs: dict = {}

    # Convert postgresql+asyncpg:// to postgresql:// (asyncpg native format)
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

    # Parse URL to extract SSL parameters
    parsed = urlparse(url)
    if parsed.query:
        query_params = parse_qs(parsed.query)

        # Extract ssl/sslmode parameters (asyncpg can't accept these in the URL)
        sslmode = query_params.pop("sslmode", [None])[0]
        ssl_param = query_params.pop("ssl", [None])[0]

        # Rebuild URL without SSL parameters
        new_query = urlencode(query_params, doseq=True) if query_params else ""
        url = urlunparse(parsed._replace(query=new_query))

        # Configure SSL context if required
        if sslmode in ("require", "verify-ca", "verify-full") or ssl_param == "require":
            ssl_context = ssl.create_default_context()
            # For 'require' mode: don't verify certificate (matches psycopg2 behavior)
            if sslmode == "require" or ssl_param == "require":
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            conn_kwargs["ssl"] = ssl_context

    return url, conn_kwargs
