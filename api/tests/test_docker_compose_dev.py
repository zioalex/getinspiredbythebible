"""
Regression tests for docker-compose.dev.yml's db-init/api contract.

These tests parse the compose file directly with PyYAML and assert on its
structure. They never invoke Docker/`docker compose` and therefore run in
any environment (CI, local, sandboxed) without a Docker daemon.

Context (BITB-092): `make docker-up-dev` starts db-init, which runs
scripts/migrations/run_migrations.py. That script resolves its `api/`
package two directories up from its own file (../../api), matching the
layout the main stack's docker-compose.yml exposes via `./api:/api:ro`.
docker-compose.dev.yml lacked that mount, so db-init's migration step
crashed with `ModuleNotFoundError: config`. Separately, the dev stack's
EMBEDDING_PROVIDER/EMBEDDING_DIMENSIONS env vars were missing or
inconsistent between the api and db-init services, causing embedding
model/dimension drift versus the main local stack (docker-compose.yml).
"""

from pathlib import Path

import pytest
import yaml

COMPOSE_PATH = Path(__file__).resolve().parent.parent.parent / "docker-compose.dev.yml"

EXPECTED_EMBEDDING_ENV = {
    "EMBEDDING_PROVIDER": "${EMBEDDING_PROVIDER:-ollama}",
    "EMBEDDING_MODEL": "${EMBEDDING_MODEL:-mxbai-embed-large}",
    "EMBEDDING_DIMENSIONS": "${EMBEDDING_DIMENSIONS:-1024}",
}


@pytest.fixture(scope="module")
def compose_config():
    """Load docker-compose.dev.yml with PyYAML (no Docker daemon needed)."""
    with open(COMPOSE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _env_list_to_dict(env_list):
    """Convert a compose `environment: [KEY=VALUE, ...]` list to a dict."""
    result = {}
    for entry in env_list:
        key, _, value = entry.partition("=")
        result[key] = value
    return result


def test_db_init_mounts_api_read_only(compose_config):
    """db-init must mount ./api at /api read-only, same contract as prod.

    run_migrations.py resolves ../../api relative to its own path inside
    /scripts, so /api must exist read-only in the container for the
    migration step to import config.py successfully.
    """
    db_init_volumes = compose_config["services"]["db-init"]["volumes"]
    assert "./api:/api:ro" in db_init_volumes, (
        "db-init is missing the './api:/api:ro' mount that "
        "run_migrations.py needs to import api/config.py "
        "(see docker-compose.yml's db-init service for the reference contract)"
    )


def test_db_init_embedding_env_matches_main_stack(compose_config):
    """db-init must carry the same embedding provider/model/dimensions defaults."""
    db_init_env = _env_list_to_dict(compose_config["services"]["db-init"]["environment"])

    for key, expected_value in EXPECTED_EMBEDDING_ENV.items():
        assert key in db_init_env, f"db-init environment is missing {key}"
        assert db_init_env[key] == expected_value, (
            f"db-init {key} default drifted: expected {expected_value!r}, "
            f"got {db_init_env[key]!r}"
        )


def test_api_embedding_env_matches_main_stack(compose_config):
    """api must carry the same embedding provider/model/dimensions defaults."""
    api_env = _env_list_to_dict(compose_config["services"]["api"]["environment"])

    for key, expected_value in EXPECTED_EMBEDDING_ENV.items():
        assert key in api_env, f"api environment is missing {key}"
        assert api_env[key] == expected_value, (
            f"api {key} default drifted: expected {expected_value!r}, " f"got {api_env[key]!r}"
        )


def test_db_init_and_api_embedding_env_are_identical(compose_config):
    """api and db-init must never disagree on embedding provider/model/dimensions."""
    api_env = _env_list_to_dict(compose_config["services"]["api"]["environment"])
    db_init_env = _env_list_to_dict(compose_config["services"]["db-init"]["environment"])

    for key in EXPECTED_EMBEDDING_ENV:
        assert api_env.get(key) == db_init_env.get(key), (
            f"api and db-init disagree on {key}: "
            f"api={api_env.get(key)!r} db-init={db_init_env.get(key)!r}"
        )
