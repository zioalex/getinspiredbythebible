#!/usr/bin/env python3
"""Probe that every configured model ID still exists at its provider (BITB-304).

Reads model IDs from the repo (never copies them):

* ``api/config.py`` Settings defaults: ``openrouter_model``,
  ``openrouter_fallback_models`` (comma separated) and
  ``language_model_overrides`` (``lang=model`` pairs)
* ``api/providers/llama_guard.py``: ``MODEL`` / ``SECONDARY_MODEL`` (routed via OpenRouter)
* ``deployment/variables.tf``: ``openrouter_model`` / ``openrouter_fallback_models`` defaults
* ``api/providers/claude.py``: ``DEFAULT_CLAUDE_MODEL``

OpenRouter IDs are checked against the public ``GET /api/v1/models`` list (no key).
The Claude default is checked against Anthropic's ``GET /v1/models`` only when
``ANTHROPIC_API_KEY`` is set; otherwise that check is reported as skipped.

It makes no completion calls.

Exit codes: 0 all present, 1 at least one ID missing, 2 network/HTTP error (kept distinct
so an outage is never read as a model retirement).

Standard library only, so the workflow needs no ``pip install``.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
ANTHROPIC_VERSION = "2023-06-01"
HTTP_TIMEOUT = 30

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_ERROR = 2


class ProbeError(Exception):
    """Network or HTTP failure while talking to a provider (exit code 2)."""


# (model id, where it came from)
ModelRef = tuple[str, str]


# ---------------------------------------------------------------------------
# Reading configured IDs
# ---------------------------------------------------------------------------
def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _settings_defaults(config_py: Path) -> dict[str, object]:
    """Literal defaults of the ``Settings`` class, read statically (no imports/env)."""
    tree = ast.parse(config_py.read_text(encoding="utf-8"))
    defaults: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and stmt.value is not None
                ):
                    try:
                        defaults[stmt.target.id] = ast.literal_eval(stmt.value)
                    except ValueError:
                        continue
    return defaults


def read_config_models(config_py: Path) -> list[ModelRef]:
    defaults = _settings_defaults(config_py)
    source = "api/config.py"
    refs: list[ModelRef] = []
    primary = defaults.get("openrouter_model")
    if isinstance(primary, str) and primary:
        refs.append((primary, f"{source} openrouter_model"))
    fallbacks = defaults.get("openrouter_fallback_models")
    if isinstance(fallbacks, str):
        refs += [(m, f"{source} openrouter_fallback_models") for m in _split_csv(fallbacks)]
    overrides = defaults.get("language_model_overrides")
    if isinstance(overrides, str):
        for pair in _split_csv(overrides):
            _, _, model = pair.partition("=")
            if model.strip():
                refs.append((model.strip(), f"{source} language_model_overrides"))
    return refs


def read_llama_guard_models(llama_guard_py: Path) -> list[ModelRef]:
    text = llama_guard_py.read_text(encoding="utf-8")
    refs: list[ModelRef] = []
    for attr in ("MODEL", "SECONDARY_MODEL"):
        match = re.search(rf'^\s*{attr}\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match:
            refs.append((match.group(1), f"api/providers/llama_guard.py {attr}"))
    return refs


def read_terraform_models(variables_tf: Path) -> list[ModelRef]:
    text = variables_tf.read_text(encoding="utf-8")
    refs: list[ModelRef] = []
    for name in ("openrouter_model", "openrouter_fallback_models"):
        block = re.search(rf'variable\s+"{name}"\s*\{{.*?default\s*=\s*"([^"]*)"', text, re.DOTALL)
        if not block:
            continue
        for model in _split_csv(block.group(1)):
            refs.append((model, f"deployment/variables.tf {name}"))
    return refs


def read_claude_default(claude_py: Path) -> list[ModelRef]:
    match = re.search(
        r'^DEFAULT_CLAUDE_MODEL\s*=\s*"([^"]+)"', claude_py.read_text(encoding="utf-8"), re.M
    )
    if not match:
        return []
    return [(match.group(1), "api/providers/claude.py DEFAULT_CLAUDE_MODEL")]


def collect_models(root: Path = REPO_ROOT) -> tuple[list[ModelRef], list[ModelRef]]:
    """Return ``(openrouter_refs, claude_refs)`` read from the repo."""
    openrouter = (
        read_config_models(root / "api" / "config.py")
        + read_llama_guard_models(root / "api" / "providers" / "llama_guard.py")
        + read_terraform_models(root / "deployment" / "variables.tf")
    )
    claude = read_claude_default(root / "api" / "providers" / "claude.py")
    return openrouter, claude


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------
def _get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ProbeError(f"HTTP {exc.code} from {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ProbeError(f"request to {url} failed: {exc}") from exc


def fetch_openrouter_ids() -> set[str]:
    payload = _get_json(OPENROUTER_MODELS_URL)
    data = payload.get("data")
    if not isinstance(data, list):
        raise ProbeError("unexpected OpenRouter response shape (no 'data' list)")
    return {item["id"] for item in data if isinstance(item, dict) and "id" in item}


def fetch_anthropic_ids(api_key: str) -> set[str]:
    headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}
    ids: set[str] = set()
    after_id: str | None = None
    while True:
        url = f"{ANTHROPIC_MODELS_URL}?limit=1000"
        if after_id:
            url += f"&after_id={after_id}"
        payload = _get_json(url, headers)
        data = payload.get("data")
        if not isinstance(data, list):
            raise ProbeError("unexpected Anthropic response shape (no 'data' list)")
        ids.update(item["id"] for item in data if isinstance(item, dict) and "id" in item)
        if not payload.get("has_more"):
            return ids
        after_id = payload.get("last_id")
        if not after_id:
            raise ProbeError("Anthropic reported has_more without last_id")


def openrouter_candidates(model_id: str) -> set[str]:
    """IDs under which an OpenRouter model may appear (tolerates an ``openrouter/`` prefix)."""
    ids = {model_id}
    if model_id.startswith("openrouter/"):
        ids.add(model_id[len("openrouter/") :])
    return ids


def find_missing(refs: list[ModelRef], available: set[str], *, openrouter: bool) -> list[ModelRef]:
    missing = []
    for model_id, source in refs:
        candidates = openrouter_candidates(model_id) if openrouter else {model_id}
        if not candidates & available:
            missing.append((model_id, source))
    return missing


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run(root: Path = REPO_ROOT, env: dict[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    openrouter_refs, claude_refs = collect_models(root)
    if not openrouter_refs:
        print("ERROR: no OpenRouter model IDs found - the parsers are out of date", file=sys.stderr)
        return EXIT_ERROR
    if not claude_refs:
        print("ERROR: Claude default model not found in api/providers/claude.py", file=sys.stderr)
        return EXIT_ERROR

    missing: list[ModelRef] = []
    try:
        available = fetch_openrouter_ids()
        missing += find_missing(openrouter_refs, available, openrouter=True)
        print(f"OpenRouter: checked {len(openrouter_refs)} configured ID(s)")

        api_key = env.get("ANTHROPIC_API_KEY", "").strip()
        if api_key:
            anthropic_ids = fetch_anthropic_ids(api_key)
            missing += find_missing(claude_refs, anthropic_ids, openrouter=False)
            print(f"Anthropic: checked {len(claude_refs)} configured ID(s)")
        else:
            print("Anthropic: skipped (ANTHROPIC_API_KEY not set)")
    except ProbeError as exc:
        print(f"ERROR: could not complete the probe: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if missing:
        for model_id, source in missing:
            print(f"MISSING: {model_id} (configured in {source})", file=sys.stderr)
        return EXIT_MISSING
    print("OK: every checked model ID exists at its provider")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(run())
