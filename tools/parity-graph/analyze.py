#!/usr/bin/env python3
"""Validate the parity registry and emit the parity graph (BITB-262, BITB-260 stage 2).

``docs/parity/registry.yaml`` is the store of record for capability × client
parity. This script is its guard and its compiler:

    python tools/parity-graph/analyze.py
        Validate the registry (JSON Schema + cross-references + evidence-path
        existence + strings cross-check) and write ``docs/parity/graph.json`` —
        the derived, deterministic artifact BITB-263's Neo4j importer consumes.

    python tools/parity-graph/analyze.py --check
        Same validation, but verify the committed ``graph.json`` matches what
        the registry would emit. Exits 1 with a diff if stale — CI's freshness
        gate. Drifted/partial/absent ROWS ARE DATA, never failures (they render
        in the job summary via ``render.py --summary``).

Validation layers
-----------------
1. **Schema** — ``tools/parity-graph/registry.schema.json`` (jsonschema,
   draft 2020-12): status vocabulary, evidence required for synced/drifted/
   partial, story required for obligated, per-client parity completeness.
2. **Cross-references** — unique contract/capability ids; every capability's
   ``contracts`` entries exist.
3. **Evidence paths** — every evidence/source_of_truth entry that looks like a
   repo path (``<root>/...`` optionally with ``:LINE`` or ``:LINE-LINE``) must
   exist on disk. A row citing a file that isn't there is exactly the
   plausible-but-wrong edge BITB-260 forbids, so it fails loud.
4. **Strings cross-check** — re-runs the Android ``translation-validation``
   CI job's own check against its own files, and refuses to disagree with it:
   the extraction regex and the locale-discovery rule are read *out of*
   ``.github/workflows/android-ci.yml`` on every run, so if that job ever
   changes, this script fails until it is updated to match — two validators
   can never silently diverge. The registry's declared locale sets
   (``contracts[].locales``) must equal the real Android and web locale sets.

Determinism
-----------
``graph.json`` sorts every list and dict key (``json.dumps(sort_keys=True)``),
so two runs on the same registry + tree produce byte-identical output — a diff
is meaningful, never churn (same rule as scripts/export_openapi.py).

Offline: no network, no database, no app import. Needs jsonschema + PyYAML
(``pip install jsonschema PyYAML``; the CI job pins both).
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent.parent
REGISTRY_PATH = REPO_ROOT / "docs" / "parity" / "registry.yaml"
GRAPH_PATH = REPO_ROOT / "docs" / "parity" / "graph.json"
SCHEMA_PATH = TOOLS_DIR / "registry.schema.json"

# The Android CI workflow whose translation-validation job is the source of
# truth for the strings cross-check (see strings_cross_check()).
ANDROID_CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "android-ci.yml"
ANDROID_RES_DIR = REPO_ROOT / "android" / "app" / "src" / "main" / "res"
ANDROID_DEFAULT_STRINGS = ANDROID_RES_DIR / "values" / "strings.xml"
WEB_MESSAGES_DIR = REPO_ROOT / "frontend" / "messages"

CLIENT_IDS = ("api", "web", "android", "ios")
STATUSES = ("synced", "drifted", "partial", "absent", "obligated", "n/a")

# Repo roots that mark an evidence string as a path to existence-check. A
# leading ``<root>/`` is unambiguous (never prose); anything else (PR refs,
# story ids, notes like "BITB-087 Tier 1") is left alone.
PATH_ROOTS = (
    "api/",
    "android/",
    "frontend/",
    "docs/",
    "tests/",
    "scripts/",
    "tools/",
    "data/",
    "deployment/",
    "infra/",
    "k8s/",
    ".github/",
)

# Optional ``:LINE`` / ``:LINE-LINE`` suffix on evidence paths
# (e.g. ``frontend/src/lib/api.ts:699``).
_LINE_SUFFIX = re.compile(r":\d+(-\d+)?$")


class ValidationError(Exception):
    """One or more registry problems; the message lists them all."""


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Parse registry.yaml; raise a readable error when PyYAML is missing."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            "analyze.py needs PyYAML — install it with `pip install PyYAML` "
            "(CI pins PyYAML==6.0.3)."
        ) from exc
    if not path.exists():
        raise SystemExit(f"registry not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Strings cross-check — same source of truth as android-ci translation-validation
# ---------------------------------------------------------------------------


def translation_validation_pattern(workflow_text: str) -> str:
    """Extract the string-name regex from the android-ci translation-validation job.

    The job (``.github/workflows/android-ci.yml``) extracts names with::

        grep -oP '(?<=<string name=")[^"]+' "$DEFAULT_FILE" | sort -u

    This function reads that pattern OUT of the live workflow file so the
    parity cross-check and the CI job are mechanically pinned together: if
    someone edits the job, every analyze.py run fails until this repo's
    cross-check is updated to match — the two validators cannot disagree.
    """
    match = re.search(r"grep -oP '([^']+)' \"\$DEFAULT_FILE\"", workflow_text)
    if not match:
        raise ValidationError(
            "cannot find the translation-validation extraction pattern in "
            f"{ANDROID_CI_WORKFLOW} — the android-ci job changed; update "
            "tools/parity-graph/analyze.py (and its tests) to match it so the "
            "two validators cannot disagree."
        )
    return match.group(1)


def _locale_dirs_with_strings() -> dict[str, Path]:
    """Locale dirs that actually contain a strings.xml — the job's own rule.

    Mirrors the workflow's discovery loop (``values-*/`` dirs with a
    ``strings.xml``), which excludes qualifier-only dirs like values-night/.
    """
    locales: dict[str, Path] = {}
    for strings_file in sorted(ANDROID_RES_DIR.glob("values-*/strings.xml")):
        locales[strings_file.parent.name.removeprefix("values-")] = strings_file
    return locales


def extract_string_names(text: str, pattern: str) -> set[str]:
    """Apply the workflow's own extraction regex to a strings.xml body."""
    return set(re.findall(pattern, text))


def strings_facts() -> dict[str, Any]:
    """Re-derive the strings-catalog facts from the same files CI validates.

    Returns the default (English) name set, the discovered Android locales with
    their name sets, the web message locales, and the missing-key report the
    translation-validation job would produce. Raises ValidationError when the
    pinned workflow pattern no longer matches the one this module uses.
    """
    if not ANDROID_CI_WORKFLOW.exists():
        raise ValidationError(f"missing {ANDROID_CI_WORKFLOW} — cannot pin the strings cross-check")
    pattern = translation_validation_pattern(ANDROID_CI_WORKFLOW.read_text(encoding="utf-8"))

    default_names = extract_string_names(
        ANDROID_DEFAULT_STRINGS.read_text(encoding="utf-8"), pattern
    )
    if not default_names:
        raise ValidationError(
            f'no <string name="..."> entries found in {ANDROID_DEFAULT_STRINGS} — '
            "the translation-validation extraction pattern does not match the file"
        )

    locales: dict[str, list[str]] = {}
    missing: dict[str, list[str]] = {}
    for locale, strings_file in _locale_dirs_with_strings().items():
        names = extract_string_names(strings_file.read_text(encoding="utf-8"), pattern)
        locales[locale] = sorted(names)
        absent = sorted(default_names - names)
        if absent:
            missing[locale] = absent

    web_locales = sorted(
        p.stem for p in WEB_MESSAGES_DIR.glob("*.json") if p.name != "package.json"
    )

    return {
        "pattern": pattern,
        "default_keys": sorted(default_names),
        "android_locales": locales,
        "web_locales": web_locales,
        "missing": missing,
    }


def check_strings(registry: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    """Strings cross-check: the registry's claims must match the files CI validates.

    Fails on (a) missing Android keys — the same gate translation-validation
    enforces, on the same inputs; (b) any contract ``locales`` declaration that
    disagrees with the discovered Android/web locale sets. Returns error
    messages (empty list = clean).
    """
    errors: list[str] = []

    for locale, absent in sorted(facts["missing"].items()):
        preview = ", ".join(absent[:5]) + (" ..." if len(absent) > 5 else "")
        errors.append(
            f"strings-catalog: android locale '{locale}' is missing {len(absent)} key(s) "
            f"({preview}) — the translation-validation CI job fails on the same gap"
        )

    android_set = set(facts["android_locales"]) | {"en"}  # default values/ is English
    web_set = set(facts["web_locales"])

    for contract in registry.get("contracts", []):
        declared = contract.get("locales")
        if not declared:
            continue
        declared_set = set(declared)
        if declared_set != android_set:
            errors.append(
                f"contract '{contract['id']}' declares locales {sorted(declared_set)} but the "
                f"Android res dirs are {sorted(android_set)}"
            )
        if declared_set != web_set:
            errors.append(
                f"contract '{contract['id']}' declares locales {sorted(declared_set)} but the "
                f"web messages/ files are {sorted(web_set)}"
            )
    return errors


# ---------------------------------------------------------------------------
# Schema + cross-reference + evidence validation
# ---------------------------------------------------------------------------


def validate_schema(registry: dict[str, Any]) -> list[str]:
    """JSON-Schema validation (registry.schema.json)."""
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            "analyze.py needs jsonschema — install it with `pip install jsonschema` "
            "(CI pins jsonschema==4.26.0)."
        ) from exc
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    problems = sorted(validator.iter_errors(registry), key=lambda e: list(e.absolute_path))
    return [
        f"schema: {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in problems
    ]


def check_cross_references(registry: dict[str, Any]) -> list[str]:
    """Uniqueness + referential integrity checks jsonschema cannot express."""
    errors: list[str] = []
    contract_ids = [c["id"] for c in registry.get("contracts", [])]
    capability_ids = [c["id"] for c in registry.get("capabilities", [])]
    for label, ids in (("contract", contract_ids), ("capability", capability_ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            errors.append(f"duplicate {label} ids: {sorted(dupes)}")
    known = set(contract_ids)
    for cap in registry.get("capabilities", []):
        for ref in cap.get("contracts", []):
            if ref not in known:
                errors.append(f"capability '{cap['id']}' references unknown contract '{ref}'")
    return errors


def _evidence_strings(cell: dict[str, Any]) -> list[str]:
    evidence = cell.get("evidence", [])
    if isinstance(evidence, str):
        return [evidence]
    return list(evidence)


def _evidence_items(registry: dict[str, Any]) -> list[tuple[str, str]]:
    """Every (owner-label, evidence-entry) pair in the registry, in stable order."""
    items: list[tuple[str, str]] = []
    for contract in registry.get("contracts", []):
        owner = f"contract '{contract['id']}'"
        for entry in contract.get("source_of_truth", []):
            items.append((f"{owner} source_of_truth", entry))
        for client, cell in (contract.get("consumers") or {}).items():
            for entry in _evidence_strings(cell):
                items.append((f"{owner} consumer '{client}'", entry))
    for cap in registry.get("capabilities", []):
        for client, cell in cap["parity"].items():
            for entry in _evidence_strings(cell):
                items.append((f"capability '{cap['id']}' parity '{client}'", entry))
    return items


def check_evidence_paths(registry: dict[str, Any]) -> list[str]:
    """Every path-like evidence entry must exist on disk (rows must be TRUE).

    An entry counts as a path when it starts with one of PATH_ROOTS; a
    trailing ``:LINE``/``:LINE-LINE`` is stripped first. Other entries (PR
    refs, story ids, notes) are untouched.
    """
    errors: list[str] = []
    for owner, entry in _evidence_items(registry):
        if not entry.startswith(PATH_ROOTS):
            continue
        path_text = _LINE_SUFFIX.sub("", entry)
        if not (REPO_ROOT / path_text).exists():
            errors.append(f"{owner}: evidence path does not exist: {path_text}")
    return errors


def validate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    """Run every validation layer; raise ValidationError listing all problems."""
    facts = strings_facts()
    errors = (
        validate_schema(registry)
        + check_cross_references(registry)
        + check_evidence_paths(registry)
        + check_strings(registry, facts)
    )
    if errors:
        raise ValidationError("docs/parity/registry.yaml is invalid:\n  - " + "\n  - ".join(errors))
    return facts


# ---------------------------------------------------------------------------
# graph.json emission (BITB-263's importer consumes this)
# ---------------------------------------------------------------------------


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _cell(cell: dict[str, Any]) -> dict[str, Any]:
    """Normalize one parity cell for the graph (deterministic key order via sort)."""
    out: dict[str, Any] = {"status": cell["status"]}
    evidence = _as_list(cell.get("evidence"))
    if evidence:
        out["evidence"] = evidence
    if "story" in cell:
        out["story"] = cell["story"]
    if "pr" in cell:
        out["pr"] = _as_list(cell["pr"])
    if "note" in cell:
        out["note"] = cell["note"]
    return out


def _client_nodes(registry: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = []
    for cid, client in registry["clients"].items():
        node: dict[str, Any] = {
            "id": f"client:{cid}",
            "label": cid,
            "kind": "client",
            "repo_path": client["repo_path"],
        }
        if "status" in client:
            node["status"] = client["status"]
        if "story" in client:
            node["story"] = client["story"]
        nodes.append(node)
    return nodes


def _contract_nodes_and_edges(
    registry: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for contract in registry["contracts"]:
        nodes.append(
            {
                "id": f"contract:{contract['id']}",
                "label": contract["id"],
                "kind": "contract",
                "description": contract["description"],
                "source_of_truth": list(contract["source_of_truth"]),
                "status": contract.get("status", "active"),
            }
        )
        for client, cell in (contract.get("consumers") or {}).items():
            edges.append(
                {
                    "from": f"client:{client}",
                    "to": f"contract:{contract['id']}",
                    "kind": "consumes",
                    **_cell(cell),
                }
            )
    return nodes, edges


def _capability_nodes_and_edges(
    registry: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for cap in registry["capabilities"]:
        cap_node: dict[str, Any] = {
            "id": f"capability:{cap['id']}",
            "label": cap["title"],
            "kind": cap.get("kind", "capability"),
            "description": cap["description"],
        }
        if cap.get("tier") is not None:
            cap_node["ios_tier"] = cap["tier"]
        nodes.append(cap_node)
        for client, cell in cap["parity"].items():
            edges.append(
                {
                    "from": f"capability:{cap['id']}",
                    "to": f"client:{client}",
                    "kind": "parity",
                    **_cell(cell),
                }
            )
        for contract in cap.get("contracts", []):
            edges.append(
                {
                    "from": f"capability:{cap['id']}",
                    "to": f"contract:{contract}",
                    "kind": "governed_by",
                }
            )
    return nodes, edges


def _drift_and_counts(registry: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Status rollup + the drifted-cell digest (stable order: STATUSES, then id)."""
    status_counts: dict[str, int] = {s: 0 for s in STATUSES}
    drifted: list[dict[str, Any]] = []
    for cap in registry["capabilities"]:
        for client, cell in cap["parity"].items():
            status_counts[cell["status"]] += 1
            if cell["status"] == "drifted":
                drifted.append(
                    {
                        "capability": cap["id"],
                        "client": client,
                        "story": cell.get("story"),
                        "note": cell.get("note"),
                        "evidence": _as_list(cell.get("evidence")),
                    }
                )
    return status_counts, drifted


def build_graph(registry: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    """Compile the registry (+ strings facts) into nodes/edges/summaries.

    Everything an importer needs is explicit: ``nodes`` (clients, contracts,
    capabilities) and ``edges`` (contract consumption, per-client parity,
    capability→contract membership), all deterministic.
    """
    contract_nodes, contract_edges = _contract_nodes_and_edges(registry)
    capability_nodes, capability_edges = _capability_nodes_and_edges(registry)
    status_counts, drifted = _drift_and_counts(registry)

    return {
        "schema_version": 1,
        "source": "docs/parity/registry.yaml",
        "registry_updated": registry["updated"],
        "clients": sorted(registry["clients"]),
        "nodes": sorted(
            _client_nodes(registry) + contract_nodes + capability_nodes,
            key=lambda n: n["id"],
        ),
        "edges": sorted(
            contract_edges + capability_edges, key=lambda e: (e["from"], e["to"], e["kind"])
        ),
        "status_counts": status_counts,
        "drifted": sorted(drifted, key=lambda d: (d["capability"], d["client"])),
        "strings_catalog": {
            "default_key_count": len(facts["default_keys"]),
            "android_locales": sorted(facts["android_locales"]),
            "web_locales": facts["web_locales"],
            "missing_by_locale": facts["missing"],
        },
    }


def render_graph_json(graph: dict[str, Any]) -> str:
    """Deterministic JSON text (all keys sorted recursively, like export_openapi)."""
    return json.dumps(graph, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_stale_diff(committed: str, regenerated: str) -> None:
    diff = difflib.unified_diff(
        committed.splitlines(keepends=True),
        regenerated.splitlines(keepends=True),
        fromfile="docs/parity/graph.json (committed)",
        tofile="regenerated",
    )
    print(
        "FAIL: docs/parity/graph.json is stale — the registry (or the strings "
        "files it embeds facts from) changed without regenerating.\n"
        "Run `python tools/parity-graph/analyze.py` and commit the result.\n",
        file=sys.stderr,
    )
    sys.stderr.writelines(diff)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed graph.json matches the registry; write nothing.",
    )
    args = parser.parse_args(argv)

    registry = load_registry()
    facts = validate_registry(registry)
    rendered = render_graph_json(build_graph(registry, facts))

    if args.check:
        committed = GRAPH_PATH.read_text(encoding="utf-8") if GRAPH_PATH.exists() else ""
        if committed != rendered:
            _print_stale_diff(committed, rendered)
            return 1
        counts = ", ".join(
            f"{s}={n}"
            for s, n in sorted(build_graph(registry, facts)["status_counts"].items())
            if n
        )
        print(
            f"OK: docs/parity/graph.json is fresh "
            f"({len(registry['contracts'])} contracts, {len(registry['capabilities'])} "
            f"capabilities; {counts})."
        )
        return 0

    GRAPH_PATH.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote docs/parity/graph.json ({len(registry['contracts'])} contracts, "
        f"{len(registry['capabilities'])} capabilities)."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
