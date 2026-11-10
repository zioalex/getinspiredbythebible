#!/usr/bin/env python3
"""Render the parity landscape (docs/parity/landscape.md) from the registry (BITB-262).

    python tools/parity-graph/render.py
        Write ``docs/parity/landscape.md``: a Mermaid container diagram (backend +
        clients + contracts — GitHub renders Mermaid natively), the contracts
        table, the capability × client status matrix, and the drift watch.

    python tools/parity-graph/render.py --check
        Verify the committed landscape matches what the registry would render;
        exit 1 with a diff if stale (CI freshness gate).

    python tools/parity-graph/render.py --summary
        Print the drift watch (drifted/partial/absent rows with stories and
        evidence) as markdown to stdout. The parity CI job appends this to
        $GITHUB_STEP_SUMMARY — the payload, never the failure: red rows stay
        visible until their story closes.

The landscape is a *view*: everything it says comes from
``docs/parity/registry.yaml`` (validated by analyze.py). Never hand-edit
``docs/parity/landscape.md`` — regenerate it.

Deterministic: content derives only from the registry (including its
``updated`` date), so two runs on the same tree are byte-identical.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent.parent
LANDSCAPE_PATH = REPO_ROOT / "docs" / "parity" / "landscape.md"

CLIENT_IDS = ("api", "web", "android", "ios")
STATUSES = ("synced", "drifted", "partial", "absent", "obligated", "n/a")
# How each status renders everywhere (matrix cells, legend, summary).
STATUS_MARKS = {
    "synced": "🟢",
    "drifted": "🔴",
    "partial": "🟡",
    "absent": "⚫",
    "obligated": "🔵",
    "n/a": "⚪",
}


def _load_registry() -> dict[str, Any]:
    """Import analyze.py's loader (single source: same validation, no fork)."""
    sys.path.insert(0, str(TOOLS_DIR))
    import analyze  # function-level sibling import, after the sys.path setup

    return analyze.load_registry()


def _mermaid_id(index: int) -> str:
    return f"c{index}"


def _contract_box_lines(
    contracts: list[dict[str, Any]],
) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """The API/SHARED/WEB boxes with their contract nodes, plus id/owner maps.

    A contract's box is derived from its first ``source_of_truth`` path's top
    directory (api/ → the backend box, frontend/ → the web box, anything else →
    the shared box) — the diagram follows the registry data, not a hand-kept
    map.
    """
    boxes: dict[str, list[str]] = {"API": [], "SHARED": [], "WEB": []}
    id_of: dict[str, str] = {}
    owner_of: dict[str, str] = {}
    labels: dict[str, str] = {}

    for index, contract in enumerate(contracts):
        node_id = _mermaid_id(index)
        id_of[contract["id"]] = node_id
        first = str(contract["source_of_truth"][0])
        owner = (
            "API"
            if first.startswith("api/")
            else ("WEB" if first.startswith("frontend/") else "SHARED")
        )
        owner_of[contract["id"]] = owner
        suffix = "" if contract.get("status", "active") == "active" else " (not landed)"
        labels[node_id] = f'{node_id}["{contract["id"]}{suffix}"]'
        boxes[owner].append(node_id)

    box_titles = {
        "API": "api — FastAPI backend (contract source)",
        "SHARED": "shared contracts (fixtures / catalog / posture)",
        "WEB": "web — frontend/",
    }
    lines: list[str] = []
    for box_id in ("API", "SHARED", "WEB"):
        lines.append(f'    subgraph {box_id}["{box_titles[box_id]}"]')
        for node_id in boxes[box_id]:
            lines.append(f"        {labels[node_id]}")
        lines.append("    end")
        lines.append("")
    return lines, id_of, owner_of


def _client_box_lines(clients: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for client_id in ("web", "android", "ios"):
        planned = " (planned, BITB-087)" if clients[client_id].get("status") == "planned" else ""
        # Client boxes carry a SUB_ prefix so their ids never collide with the
        # owner boxes above (the web box already exists for web-owned contracts).
        lines.append(f'    subgraph SUB_{client_id.upper()}["{client_id}{planned}"]')
        lines.append("    end")
        lines.append("")
    return lines


def _edge_lines(
    contracts: list[dict[str, Any]], id_of: dict[str, str], owner_of: dict[str, str]
) -> list[str]:
    lines: list[str] = []
    for contract in contracts:
        node_id = id_of[contract["id"]]
        for client_id, cell in (contract.get("consumers") or {}).items():
            if client_id == "api" and owner_of[contract["id"]] == "API":
                continue  # the backend box already owns the contract; no self-edge
            if cell["status"] == "n/a":
                continue
            source = "API" if client_id == "api" else f"SUB_{client_id.upper()}"
            lines.append(f'    {source} -->|"{cell["status"]}"| {node_id}')
    return lines


def render_mermaid(registry: dict[str, Any]) -> str:
    """The container diagram: contracts live in their owner's box; clients connect.

    Consumer edges carry the parity status; n/a edges are omitted. The ios box
    is dashed (planned, BITB-087).
    """
    box_lines, id_of, owner_of = _contract_box_lines(registry["contracts"])
    lines = ["flowchart LR", ""]
    lines.extend(box_lines)
    lines.extend(_client_box_lines(registry["clients"]))
    lines.extend(_edge_lines(registry["contracts"], id_of, owner_of))
    lines.append("    classDef planned stroke-dasharray: 5 5")
    lines.append("    class SUB_IOS planned")
    return "\n".join(lines)


def render_contracts_table(registry: dict[str, Any]) -> str:
    lines = [
        "| Contract | Source of truth | api | web | android | ios |",
        "|---|---|---|---|---|---|",
    ]
    for contract in registry["contracts"]:
        truth = ", ".join(f"`{t}`" for t in contract["source_of_truth"])
        row = [f"`{contract['id']}`", truth]
        consumers = contract.get("consumers") or {}
        for client_id in CLIENT_IDS:
            cell = consumers.get(client_id)
            if cell is None:
                row.append("—")
                continue
            mark = STATUS_MARKS[cell["status"]]
            story = cell.get("story")
            row.append(f"{mark} {cell['status']}" + (f" ({story})" if story else ""))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _cell_label(cell: dict[str, Any]) -> str:
    mark = STATUS_MARKS[cell["status"]]
    parts = [f"{mark} {cell['status']}"]
    if "story" in cell:
        parts.append(f"({cell['story']})")
    elif cell["status"] == "synced" and "pr" in cell:
        prs = cell["pr"]
        prs = prs if isinstance(prs, list) else [prs]
        parts.append("(" + ", ".join(f"#{p}" for p in prs) + ")")
    return " ".join(parts)


def render_matrix(registry: dict[str, Any]) -> str:
    lines = [
        "| Capability | api | web | android | ios |",
        "|---|---|---|---|---|",
    ]
    for cap in registry["capabilities"]:
        kind_suffix = " *(negative obligation)*" if cap.get("kind") == "negative-obligation" else ""
        title = f"**{cap['title']}**{kind_suffix}<br/>`{cap['id']}`"
        row = [title]
        for client_id in CLIENT_IDS:
            row.append(_cell_label(cap["parity"][client_id]))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _iter_watch_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Every non-synced, non-obligated, non-n/a cell — the actionable rows."""
    rows = []
    for cap in registry["capabilities"]:
        for client_id in CLIENT_IDS:
            cell = cap["parity"][client_id]
            if cell["status"] in ("synced", "obligated", "n/a"):
                continue
            evidence = cell.get("evidence", [])
            if isinstance(evidence, str):
                evidence = [evidence]
            rows.append(
                {
                    "capability": cap["id"],
                    "title": cap["title"],
                    "client": client_id,
                    "status": cell["status"],
                    "story": cell.get("story"),
                    "note": cell.get("note"),
                    "evidence": evidence,
                }
            )
    rows.sort(key=lambda r: (r["status"], r["capability"], r["client"]))
    return rows


def render_drift_watch(registry: dict[str, Any], heading_level: str = "##") -> str:
    """The payload section: drifted/partial/absent rows, surfaced not buried."""
    rows = _iter_watch_rows(registry)
    by_status: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_status.setdefault(row["status"], []).append(row)

    lines: list[str] = []
    if not rows:
        lines.append(f"{heading_level} Drift watch")
        lines.append("")
        lines.append(
            "No drifted, partial, or absent rows — every client cell is synced, "
            "obligated, or n/a."
        )
        return "\n".join(lines)

    lines.append(f"{heading_level} Drift watch")
    lines.append("")
    lines.append(
        "The rows below are the registry's payload, not CI failures — each stays visible "
        "until its story closes. Drifted rows are the loudest; partial and absent are the "
        "backlog's shape."
    )
    for status in ("drifted", "partial", "absent"):
        entries = by_status.get(status, [])
        if not entries:
            continue
        noun = {"drifted": "drifted", "partial": "partial", "absent": "absent"}[status]
        lines.append("")
        lines.append(f"{heading_level} {noun.capitalize()} ({len(entries)})")
        lines.append("")
        for row in entries:
            story = f" — **{row['story']}**" if row["story"] else ""
            lines.append(
                f"- {STATUS_MARKS[status]} **`{row['capability']}`** · {row['client']}{story}"
            )
            if row["note"]:
                lines.append(f"  - {row['note']}")
            for item in row["evidence"]:
                lines.append(f"  - evidence: `{item}`")
    return "\n".join(lines)


def render_landscape(registry: dict[str, Any]) -> str:
    caps = registry["capabilities"]
    n_negative = sum(1 for c in caps if c.get("kind") == "negative-obligation")
    counts: dict[str, int] = {s: 0 for s in STATUSES}
    for cap in caps:
        for cell in cap["parity"].values():
            counts[cell["status"]] += 1

    out = [
        "# Cross-Client Parity Landscape",
        "",
        f"> Generated from [`docs/parity/registry.yaml`](registry.yaml) (BITB-262, updated "
        f"{registry['updated']}) by `tools/parity-graph/render.py` — do not edit; regenerate.",
        "",
        f"{len(caps)} capabilities ({n_negative} negative obligations) × 4 clients. "
        "Evidence for every cell lives in the registry; this page is the view.",
        "",
        "## Status legend",
        "",
    ]
    for status in STATUSES:
        meaning = {
            "synced": "implemented, at parity with the reference behavior",
            "drifted": "implementations diverged; a story tracks the gap",
            "partial": "exists, open follow-ups remain",
            "absent": "not implemented on this client (or nowhere yet)",
            "obligated": "a planned client's spec requires it (BITB-087)",
            "n/a": "does not apply to this client",
        }[status]
        out.append(f"- {STATUS_MARKS[status]} **{status}** — {meaning}.")
    out.extend(
        [
            "",
            "## Container diagram",
            "",
            "Contracts live in the box that owns their source of truth; client boxes "
            "connect with their consumption status. `ios` is planned (BITB-087) — dashed.",
            "",
            "```mermaid",
            render_mermaid(registry),
            "```",
            "",
            "## Contracts",
            "",
            render_contracts_table(registry),
            "",
            "## Capability × client status matrix",
            "",
            render_matrix(registry),
            "",
            render_drift_watch(registry, heading_level="##"),
            "",
            "## Status rollup",
            "",
            "| Status | Cells |",
            "|---|---|",
        ]
    )
    for status in STATUSES:
        out.append(f"| {STATUS_MARKS[status]} {status} | {counts[status]} |")
    out.extend(
        [
            "",
            "---",
            "",
            "Regenerate with `python tools/parity-graph/render.py` (or "
            "`make parity-registry-check` to freshness-check). Part of the "
            "cross-client parity knowledge graph (BITB-260 stage 2).",
            "",
        ]
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed landscape matches the registry; write nothing.",
    )
    mode.add_argument(
        "--summary",
        action="store_true",
        help="Print the drift-watch markdown to stdout (for CI's job summary).",
    )
    args = parser.parse_args(argv)

    registry = _load_registry()

    if args.summary:
        print(render_drift_watch(registry, heading_level="##"))
        return 0

    rendered = render_landscape(registry)
    if args.check:
        committed = LANDSCAPE_PATH.read_text(encoding="utf-8") if LANDSCAPE_PATH.exists() else ""
        if committed != rendered:
            diff = difflib.unified_diff(
                committed.splitlines(keepends=True),
                rendered.splitlines(keepends=True),
                fromfile="docs/parity/landscape.md (committed)",
                tofile="regenerated",
            )
            print(
                "FAIL: docs/parity/landscape.md is stale — the registry changed "
                "without re-rendering.\n"
                "Run `python tools/parity-graph/render.py` and commit the result.\n",
                file=sys.stderr,
            )
            sys.stderr.writelines(diff)
            return 1
        print("OK: docs/parity/landscape.md is fresh.")
        return 0

    LANDSCAPE_PATH.write_text(rendered, encoding="utf-8")
    print("Wrote docs/parity/landscape.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
