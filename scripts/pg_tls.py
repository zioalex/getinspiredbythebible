"""TLS root-certificate defaults for the operator export scripts (psycopg2 / libpq).

Azure Database for PostgreSQL chains to DigiCert Global Root G2 and, since the 2026 CA
rotation, to ``Microsoft RSA Root Certificate Authority 2017``. The latter is missing from
many OS and Mozilla trust stores, and ``psycopg2-binary`` bundles its own OpenSSL that
often cannot read the OS store at all, so ``sslrootcert=system`` fails with
``SSL error: certificate verify failed`` on a fresh machine.

``default_sslrootcert()`` returns an explicit CA file that always works: certifi's bundle
(contains DigiCert Global Root G2) plus the vendored Microsoft root in
``scripts/certs/``. Used by export_feedback.py, export_blocked_samples.py and
export_retrieval_misses.py.
"""

from __future__ import annotations

import atexit
import os
import tempfile
from pathlib import Path

_MS_ROOT = Path(__file__).resolve().parent / "certs" / "microsoft-rsa-root-2017.pem"
_cached: str | None = None


def _cleanup(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def default_sslrootcert() -> str | None:
    """Value for ``sslrootcert`` when the caller did not set one.

    ``None`` means "leave it unset": the user's own ``~/.postgresql/root.crt`` exists and
    libpq will use it. Otherwise a combined CA bundle path, or ``"system"`` (OS trust
    store, libpq >= 16) if the bundle cannot be built.
    """
    global _cached
    if (Path.home() / ".postgresql" / "root.crt").is_file():
        return None
    if _cached and os.path.exists(_cached):
        return _cached
    try:
        import certifi

        data = Path(certifi.where()).read_text() + "\n" + _MS_ROOT.read_text()
        fd, path = tempfile.mkstemp(prefix="vq-azure-pg-ca-", suffix=".pem")  # 0600, unique
        with os.fdopen(fd, "w") as fh:
            fh.write(data)
        atexit.register(_cleanup, path)
        _cached = path
        return path
    except (ImportError, OSError):
        return "system"
