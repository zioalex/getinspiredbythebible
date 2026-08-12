"""BITB-059 Phase 2 — contract test between the client bundle map and the backend registry.

``tests/fixtures/localized_book_map.json`` (generated into the Android and web bundles by
``scripts/generate_localized_book_map.py``) and ``api/utils/translation_registry.py`` (via its
derived ``LOCALIZED_TO_ENGLISH`` reverse map) are two independent masters — the registry carries
per-translation-code, case-preserving data the flat lowercase JSON structurally cannot represent,
so neither generates the other (see the BITB-059 story). This test instead holds the two
contradiction-free: any key present on both sides must resolve to the same English book, and any
key present on only one side must be an explicitly reviewed, listed gap in
``tests/fixtures/localized_book_map_registry_gaps.json`` — so a new one-sided key can't ship
silently, and a closed gap can't rot in the allowlist forever.
"""

import json
from pathlib import Path

from utils.book_names import LOCALIZED_TO_ENGLISH

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JSON_PATH = _REPO_ROOT / "tests/fixtures/localized_book_map.json"
_GAPS_PATH = _REPO_ROOT / "tests/fixtures/localized_book_map_registry_gaps.json"

with open(_JSON_PATH, encoding="utf-8") as f:
    _CLIENT_MAP = json.load(f)["book_map"]

with open(_GAPS_PATH, encoding="utf-8") as f:
    _GAPS = json.load(f)["gaps"]


def _registry_lower() -> dict[str, str]:
    return {k.lower(): v.lower() for k, v in LOCALIZED_TO_ENGLISH.items()}


def _allowlisted(direction: str) -> set[str]:
    keys: set[str] = set()
    for group in _GAPS:
        if group["direction"] == direction:
            keys.update(group["keys"])
    return keys


def test_registry_lowercasing_is_not_lossy():
    """Lowercasing LOCALIZED_TO_ENGLISH's keys must not collide two distinct entries —
    otherwise the comparison below would silently drop data."""
    lowered_keys = [k.lower() for k in LOCALIZED_TO_ENGLISH]
    assert len(lowered_keys) == len(set(lowered_keys)), (
        "Two or more LOCALIZED_TO_ENGLISH keys collide after lowercasing — "
        "the case-insensitive comparison below would be unreliable."
    )


def test_no_contradictory_values():
    """Every key shared between the client map and the registry must resolve to the same
    English book. This is the real drift guard: a contradiction here means a citation would
    parse to a different book depending on which platform handled it."""
    registry = _registry_lower()
    shared = set(_CLIENT_MAP) & set(registry)
    mismatches = [
        (key, _CLIENT_MAP[key], registry[key])
        for key in shared
        if _CLIENT_MAP[key] != registry[key]
    ]
    assert not mismatches, (
        "Client map and registry disagree on the English book for these keys "
        "(key, client_value, registry_value): " + repr(mismatches)
    )


def test_one_sided_keys_are_allowlisted():
    """Every key present on only one side must be explicitly listed in
    localized_book_map_registry_gaps.json with a reviewed reason — otherwise a new alias
    added to one side without the other ships as a silent gap."""
    registry = _registry_lower()
    json_only = set(_CLIENT_MAP) - set(registry)
    registry_only = set(registry) - set(_CLIENT_MAP)

    unlisted_json_only = json_only - _allowlisted("json_only")
    unlisted_registry_only = registry_only - _allowlisted("registry_only")

    assert not unlisted_json_only, (
        "These keys exist in tests/fixtures/localized_book_map.json but not in the registry, "
        "and are not listed in localized_book_map_registry_gaps.json's 'json_only' group. "
        "Either propagate them to api/utils/translation_registry.py or add them to the "
        f"allowlist with a reason: {sorted(unlisted_json_only)!r}"
    )
    assert not unlisted_registry_only, (
        "These keys exist in the registry but not in "
        "tests/fixtures/localized_book_map.json, and are not listed in "
        "localized_book_map_registry_gaps.json's 'registry_only' group. Either propagate "
        "them to the JSON (then regenerate the Android/web maps) or add them to the "
        f"allowlist with a reason: {sorted(unlisted_registry_only)!r}"
    )


def test_allowlist_has_no_stale_entries():
    """Every allowlisted key must still actually be one-sided — otherwise the allowlist rots
    and silently stops testing anything for that key once the gap is closed elsewhere."""
    registry = _registry_lower()
    json_only = set(_CLIENT_MAP) - set(registry)
    registry_only = set(registry) - set(_CLIENT_MAP)

    stale_json_only = _allowlisted("json_only") - json_only
    stale_registry_only = _allowlisted("registry_only") - registry_only

    assert not stale_json_only, (
        "These keys are allowlisted as 'json_only' but are no longer one-sided (the gap was "
        f"closed) — remove them from localized_book_map_registry_gaps.json: {sorted(stale_json_only)!r}"
    )
    assert not stale_registry_only, (
        "These keys are allowlisted as 'registry_only' but are no longer one-sided (the gap "
        f"was closed) — remove them from localized_book_map_registry_gaps.json: {sorted(stale_registry_only)!r}"
    )
