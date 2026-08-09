"""
Tests for scripts/load_bible.py's Bible translation JSON path resolution.

Context (BITB-092 follow-up): db-init runs as a non-root container user (UID 1000) while the
host-owned `./data` bind mount is UID 1002. When `data/bible/translations/kjv.json` doesn't exist
yet, `scripts/load_bible.py` downloaded KJV successfully but then crashed with a `PermissionError`
trying to write the result into the read-write-but-not-writable-by-this-uid bind mount.

The fix mounts `./data` read-only in both compose files and introduces `BIBLE_DOWNLOAD_CACHE_DIR`,
an explicit opt-in env var pointing downloads at a writable cache directory instead. The committed
`data/bible/translations/*.json` source files (including manual-only Hindi/Luther data with no
download URL) always remain the primary read source when present.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

# Add scripts directory to path (mirrors api/tests/test_translations.py's import pattern)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from load_bible import download_translation, resolve_bible_data_path


def test_resolve_prefers_existing_primary_path_even_with_cache_configured(tmp_path, monkeypatch):
    """The committed source file always wins when it exists, cache configured or not.

    This is what keeps manual-only translations (Hindi, Luther 1912) working: they have no
    download URL, so their only data source is the committed file.
    """
    primary = tmp_path / "primary" / "kjv.json"
    primary.parent.mkdir(parents=True)
    primary.write_text("[]", encoding="utf-8")

    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("BIBLE_DOWNLOAD_CACHE_DIR", str(cache_dir))

    resolved = resolve_bible_data_path("kjv", primary)

    assert resolved == primary


def test_resolve_uses_configured_cache_when_primary_missing(tmp_path, monkeypatch):
    """A missing source file with BIBLE_DOWNLOAD_CACHE_DIR set writes to the cache instead."""
    primary = tmp_path / "primary" / "kjv.json"  # never created
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("BIBLE_DOWNLOAD_CACHE_DIR", str(cache_dir))

    resolved = resolve_bible_data_path("kjv", primary)

    assert resolved == cache_dir / "kjv.json"


def test_resolve_falls_back_to_primary_path_without_cache_configured(tmp_path, monkeypatch):
    """Unset BIBLE_DOWNLOAD_CACHE_DIR preserves the historical bare-host default path/behavior."""
    primary = tmp_path / "primary" / "kjv.json"  # never created
    monkeypatch.delenv("BIBLE_DOWNLOAD_CACHE_DIR", raising=False)

    resolved = resolve_bible_data_path("kjv", primary)

    assert resolved == primary


@pytest.mark.asyncio
async def test_download_translation_writes_to_resolved_writable_path(tmp_path, monkeypatch):
    """Downloading a missing translation writes into BIBLE_DOWNLOAD_CACHE_DIR, not the (here,
    intentionally non-writable-by-design) primary directory, and never touches the network.
    """
    primary = tmp_path / "primary" / "kjv.json"  # never created; parent dir also absent
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("BIBLE_DOWNLOAD_CACHE_DIR", str(cache_dir))

    resolved_path = resolve_bible_data_path("kjv", primary)
    assert resolved_path == cache_dir / "kjv.json"

    fake_payload = [{"name": "Genesis", "chapters": [["In the beginning..."]]}]
    mock_response = httpx.Response(
        status_code=200,
        json=fake_payload,
        request=httpx.Request("GET", "https://example.invalid/kjv.json"),
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        data = await download_translation("kjv", resolved_path)

    assert data == fake_payload
    assert resolved_path.exists(), "download_translation must write into the resolved cache path"
    assert json.loads(resolved_path.read_text(encoding="utf-8")) == fake_payload
    # The primary (source-of-truth) directory must never have been created/written to.
    assert not primary.exists()
    assert not primary.parent.exists()
