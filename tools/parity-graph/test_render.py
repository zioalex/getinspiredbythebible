#!/usr/bin/env python3
"""Tests for tools/parity-graph/render.py — offline.

Run with pytest (repo venv) or bare python3:

    python -m pytest tools/parity-graph/ -q
    python3 tools/parity-graph/test_render.py

Covers: the matrix and drift-watch render from the real registry, the Mermaid
diagram stays structurally valid (unique ids, resolvable edges, balanced
quotes — the subset GitHub renders), --summary matches the drift watch, and
the --check freshness gate fails on a stale landscape.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent.parent
sys.path.insert(0, str(TOOLS_DIR))

import analyze  # noqa: E402
import render  # noqa: E402


def real_registry() -> dict:
    return analyze.load_registry(analyze.REGISTRY_PATH)


class LandscapeRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = real_registry()
        cls.landscape = render.render_landscape(cls.registry)

    def test_committed_landscape_is_fresh(self):
        committed = render.LANDSCAPE_PATH.read_text(encoding="utf-8")
        self.assertEqual(committed, self.landscape)

    def test_deterministic(self):
        self.assertEqual(render.render_landscape(self.registry), self.landscape)

    def test_matrix_covers_every_capability_and_client(self):
        matrix = render.render_matrix(self.registry)
        for cap in self.registry["capabilities"]:
            self.assertIn(f"`{cap['id']}`", matrix)
        for client in ("api", "web", "android", "ios"):
            self.assertIn(client, matrix)
        # One header + one separator + one row per capability.
        self.assertEqual(len(matrix.splitlines()), 2 + len(self.registry["capabilities"]))

    def test_drift_watch_payload(self):
        watch = render.render_drift_watch(self.registry)
        for row in render._iter_watch_rows(self.registry):
            self.assertIn(f"**`{row['capability']}`**", watch)
            self.assertIn(f"· {row['client']}", watch)
        # Non-watch statuses must not be listed as rows.
        self.assertNotIn("🟢", watch)
        # The live backend drift renders red with its story.
        self.assertIn("**`verse-reference-detection`** · api", watch)
        self.assertIn("**BITB-267**", watch)
        # Subordinate evidence lines are present for spot-checking.
        self.assertRegex(watch, r"evidence: `api/utils/verse_parser.py:\d+`")

    def test_summary_matches_drift_watch(self):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(render.main(["--summary"]), 0)
        self.assertEqual(out.getvalue().strip(), render.render_drift_watch(self.registry).strip())


class MermaidDiagramTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diagram = render.render_mermaid(real_registry())

    def test_flowchart_header(self):
        self.assertTrue(self.diagram.startswith("flowchart LR"))

    def test_structurally_valid(self):
        """Unique subgraph/node ids, balanced quotes, resolvable edges."""
        ids = re.findall(
            r"^\s*(?:subgraph )?([A-Za-z_][A-Za-z0-9_]*)\[", self.diagram, re.MULTILINE
        )
        self.assertEqual(len(ids), len(set(ids)), f"duplicate mermaid ids: {ids}")
        declared = set(ids)
        for line in self.diagram.splitlines():
            self.assertEqual(line.count('"') % 2, 0, f"unbalanced quotes: {line}")
        for source, target in re.findall(
            r"^    (\w+) -->\|[^|]*\| (\w+)$", self.diagram, re.MULTILINE
        ):
            self.assertIn(source, declared)
            self.assertIn(target, declared)

    def test_all_contracts_and_clients_present(self):
        for contract in real_registry()["contracts"]:
            self.assertIn(f'"{contract["id"]}', self.diagram)
        for client in ("SUB_WEB", "SUB_ANDROID", "SUB_IOS"):
            self.assertIn(f"subgraph {client}[", self.diagram)

    def test_ios_box_is_dashed_planned(self):
        self.assertIn('subgraph SUB_IOS["ios (planned, BITB-087)"]', self.diagram)
        self.assertIn("classDef planned stroke-dasharray: 5 5", self.diagram)
        self.assertIn("class SUB_IOS planned", self.diagram)

    def test_n_a_edges_omitted_and_statuses_labeled(self):
        self.assertNotIn('|"n/a"|', self.diagram)
        for status in ("synced", "partial", "absent", "obligated"):
            self.assertIn(f'|"{status}"|', self.diagram)
        self.assertIn('|"drifted"|', self.diagram)  # no live consumer drift today; keep supported

    def test_contracts_grouped_by_source_of_truth_owner(self):
        # api-owned contracts sit in the API box; the web-owned legal-urls in the WEB box.
        api_box = self.diagram.split('subgraph API["')[1].split("\n    end")[0]
        self.assertIn('"chat-stream-sse"', api_box)
        web_box = self.diagram.split('subgraph WEB["')[1].split("\n    end")[0]
        self.assertIn('"legal-urls"', web_box)


class CliCheckTest(unittest.TestCase):
    def test_check_passes_on_fresh_tree(self):
        self.assertEqual(render.main(["--check"]), 0)

    def test_check_fails_on_stale_landscape(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "landscape.md"
            stale.write_text("# stale\n")
            with mock.patch.object(render, "LANDSCAPE_PATH", stale):
                self.assertEqual(render.main(["--check"]), 1)

    def test_write_emits_landscape(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "landscape.md"
            with mock.patch.object(render, "LANDSCAPE_PATH", out):
                self.assertEqual(render.main([]), 0)
                text = out.read_text(encoding="utf-8")
                self.assertIn("# Cross-Client Parity Landscape", text)
                self.assertIn("```mermaid", text)


if __name__ == "__main__":
    unittest.main()
