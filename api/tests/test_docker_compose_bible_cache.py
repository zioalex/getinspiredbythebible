"""
Regression tests for the db-init data bind-mount / BIBLE_DOWNLOAD_CACHE_DIR contract shared by
docker-compose.yml (main local stack) and docker-compose.dev.yml (second dev stack).

These tests parse the compose files directly with PyYAML and assert on structure. They never
invoke Docker/`docker compose`, so they run in any environment (CI, local, sandboxed) without a
Docker daemon.

Context (BITB-092 follow-up): db-init runs as a non-root container user (UID 1000, see
api/Dockerfile) while the host-owned `./data` bind mount can be owned by a different host UID
(observed: 1002). When `data/bible/translations/kjv.json` doesn't exist yet,
`scripts/load_bible.py` downloaded KJV successfully but then crashed with a PermissionError trying
to write the result back into `./data`, which db-init doesn't own.

The fix: mount `./data` read-only in both compose files (the committed
`data/bible/translations/*.json` files, including manual-only Hindi/Luther data with no download
URL, are read-only source data and never need to be written by db-init) and set
`BIBLE_DOWNLOAD_CACHE_DIR=/tmp/bible-translations` so first-run downloads land in a writable
location instead (see `scripts/load_bible.py`'s `resolve_bible_data_path()`).
"""

import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

COMPOSE_FILES = ["docker-compose.yml", "docker-compose.dev.yml"]

EXPECTED_CACHE_DIR = str(Path(tempfile.gettempdir()) / "bible-translations")


def _load_compose(filename: str) -> dict:
    with open(REPO_ROOT / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _env_list_to_dict(env_list):
    """Convert a compose `environment: [KEY=VALUE, ...]` list to a dict."""
    result = {}
    for entry in env_list:
        key, _, value = entry.partition("=")
        result[key] = value
    return result


@pytest.mark.parametrize("compose_file", COMPOSE_FILES)
def test_db_init_data_mount_is_read_only(compose_file):
    """db-init must mount ./data read-only; it never needs write access to committed source data.

    db-init runs as UID 1000 (api/Dockerfile) which does not necessarily own the host-owned
    ./data bind mount, so a writable mount risks a PermissionError the moment a translation
    needs downloading (e.g. first-run KJV). Downloads go to BIBLE_DOWNLOAD_CACHE_DIR instead.
    """
    compose_config = _load_compose(compose_file)
    db_init_volumes = compose_config["services"]["db-init"]["volumes"]

    assert "./data:/data:ro" in db_init_volumes, (
        f"{compose_file}'s db-init must mount './data:/data:ro' (read-only) — found volumes: "
        f"{db_init_volumes!r}"
    )
    assert (
        "./data:/data" not in db_init_volumes
    ), f"{compose_file}'s db-init must not also mount './data:/data' read-write"


@pytest.mark.parametrize("compose_file", COMPOSE_FILES)
def test_db_init_configures_bible_download_cache_dir(compose_file):
    """db-init must set BIBLE_DOWNLOAD_CACHE_DIR so downloads avoid the read-only ./data mount."""
    compose_config = _load_compose(compose_file)
    db_init_env = _env_list_to_dict(compose_config["services"]["db-init"]["environment"])

    assert "BIBLE_DOWNLOAD_CACHE_DIR" in db_init_env, (
        f"{compose_file}'s db-init is missing BIBLE_DOWNLOAD_CACHE_DIR, required now that "
        "./data is mounted read-only"
    )
    assert db_init_env["BIBLE_DOWNLOAD_CACHE_DIR"] == EXPECTED_CACHE_DIR, (
        f"{compose_file}'s db-init BIBLE_DOWNLOAD_CACHE_DIR drifted: expected "
        f"{EXPECTED_CACHE_DIR!r}, got {db_init_env['BIBLE_DOWNLOAD_CACHE_DIR']!r}"
    )


@pytest.mark.parametrize("compose_file", COMPOSE_FILES)
def test_db_init_still_mounts_api_read_only(compose_file):
    """Sanity check: the pre-existing ./api:/api:ro contract (BITB-092) must remain intact."""
    compose_config = _load_compose(compose_file)
    db_init_volumes = compose_config["services"]["db-init"]["volumes"]

    assert "./api:/api:ro" in db_init_volumes
