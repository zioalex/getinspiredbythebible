#!/usr/bin/env python3
"""Tests for tools/parity-graph/analyze.py — offline, no network, no DB.

Run with pytest (the repo venv has jsonschema + PyYAML) or bare python3:

    python -m pytest tools/parity-graph/ -q
    python3 tools/parity-graph/test_analyze.py

The integration tests validate the REAL registry against the REAL repo files —
that is the point of the tool — and pin the strings cross-check to the REAL
android-ci.yml workflow so the two validators can never silently disagree.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent.parent
sys.path.insert(0, str(TOOLS_DIR))

import analyze  # noqa: E402


def load_real_registry() -> dict:
    return analyze.load_registry(analyze.REGISTRY_PATH)


class RealRegistryIntegrationTest(unittest.TestCase):
    """The committed registry must validate end-to-end against the real tree."""

    def test_real_registry_validates(self):
        facts = analyze.validate_registry(load_real_registry())
        # Strings cross-check ran against the real files.
        self.assertEqual(facts["missing"], {})
        self.assertEqual(len(facts["default_keys"]), 291)

    def test_committed_graph_json_is_fresh(self):
        registry = load_real_registry()
        facts = analyze.validate_registry(registry)
        rendered = analyze.render_graph_json(analyze.build_graph(registry, facts))
        committed = analyze.GRAPH_PATH.read_text(encoding="utf-8")
        self.assertEqual(committed, rendered)

    def test_graph_shape(self):
        registry = load_real_registry()
        graph = analyze.build_graph(registry, analyze.strings_facts())
        self.assertEqual(graph["schema_version"], 1)
        self.assertEqual(graph["source"], "docs/parity/registry.yaml")
        self.assertEqual(sorted(graph["clients"]), ["android", "api", "ios", "web"])
        # 4 clients + 8 contracts + 33 capabilities + 2 negative obligations
        node_kinds = {}
        for node in graph["nodes"]:
            node_kinds[node["kind"]] = node_kinds.get(node["kind"], 0) + 1
        self.assertEqual(node_kinds["client"], 4)
        self.assertEqual(node_kinds["contract"], 8)
        self.assertEqual(node_kinds["capability"], 33)
        self.assertEqual(node_kinds["negative-obligation"], 2)
        # Edges: contract consumers + per-client parity + capability→contract.
        kinds = {edge["kind"] for edge in graph["edges"]}
        self.assertEqual(kinds, {"consumes", "parity", "governed_by"})

    def test_every_capability_statused_for_all_four_clients(self):
        registry = load_real_registry()
        for cap in registry["capabilities"]:
            self.assertEqual(sorted(cap["parity"]), ["android", "api", "ios", "web"], cap["id"])
            for cell in cap["parity"].values():
                self.assertIn(cell["status"], analyze.STATUSES)

    def test_bitb_042_row_exists_with_story_link_and_android_evidence(self):
        registry = load_real_registry()
        row = next(c for c in registry["capabilities"] if c["id"] == "feedback-rethink")
        android = row["parity"]["android"]
        self.assertEqual(android["status"], "synced")  # re-verified: drift closed (PR #685)
        self.assertEqual(android["story"], "BITB-042")
        self.assertEqual(android["pr"], [685, 692, 696, 783])
        for path in android["evidence"]:
            checkable = analyze._LINE_SUFFIX.sub("", path)
            self.assertTrue((REPO_ROOT / checkable).exists(), f"missing evidence: {checkable}")

    def test_live_drift_surfaces_as_red_row(self):
        """BITB-267: the backend parser drift must be recorded as drifted, not prose."""
        registry = load_real_registry()
        row = next(c for c in registry["capabilities"] if c["id"] == "verse-reference-detection")
        api_cell = row["parity"]["api"]
        self.assertEqual(api_cell["status"], "drifted")
        self.assertEqual(api_cell["story"], "BITB-267")

    def test_negative_obligations_present(self):
        registry = load_real_registry()
        neg = [c for c in registry["capabilities"] if c.get("kind") == "negative-obligation"]
        self.assertEqual(
            sorted(c["id"] for c in neg), ["ios-no-donate-entry", "ios-no-verse-regex"]
        )

    def test_wip_plan_gaps_all_covered(self):
        """Every GAP-001..012 of docs/WIP/android-feature-parity-plan.md has a row."""
        registry = load_real_registry()
        gaps: set[str] = set()
        for cap in registry["capabilities"]:
            origin = cap.get("origin") or {}
            gaps.update(origin.get("gaps", []))
        self.assertEqual(gaps, {f"GAP-{i:03d}" for i in range(1, 13)})

    def test_bitb_087_tier1_rows_obligate_ios(self):
        """Every capability mapped to BITB-087 Tier 1 obligates the iOS cell."""
        registry = load_real_registry()
        tier1 = [c for c in registry["capabilities"] if c.get("tier") == 1]
        self.assertGreaterEqual(len(tier1), 10)
        for cap in tier1:
            self.assertEqual(
                cap["parity"]["ios"]["status"],
                "obligated",
                f"{cap['id']}: Tier 1 ⇒ ios obligated",
            )
            self.assertEqual(cap["parity"]["ios"]["story"], "BITB-087")

    def test_tier2_rows_defer_ios_by_decision(self):
        registry = load_real_registry()
        tier2 = [c for c in registry["capabilities"] if c.get("tier") == 2]
        self.assertGreaterEqual(len(tier2), 8)
        for cap in tier2:
            self.assertEqual(cap["parity"]["ios"]["status"], "n/a", cap["id"])
            self.assertIn("deferred", cap["parity"]["ios"]["note"])


class StringsCrossCheckTest(unittest.TestCase):
    """The strings cross-check reuses translation-validation's source of truth."""

    def test_extraction_pattern_pinned_to_the_live_workflow(self):
        """analyze.py's pattern is read OUT of android-ci.yml — same source of truth."""
        workflow = analyze.ANDROID_CI_WORKFLOW.read_text(encoding="utf-8")
        pattern = analyze.translation_validation_pattern(workflow)
        self.assertEqual(pattern, r'(?<=<string name=")[^"]+')

    def test_changed_workflow_pattern_fails_loud(self):
        """If android-ci's job changes its extraction, analyze must refuse to run."""
        mutated = analyze.ANDROID_CI_WORKFLOW.read_text(encoding="utf-8").replace(
            "grep -oP", "grep -oX"
        )
        with self.assertRaises(analyze.ValidationError):
            analyze.translation_validation_pattern(mutated)

    def test_extraction_matches_the_ci_jobs_regex(self):
        text = '<resources>\n  <string name="app_name">Vox Quieta</string>\n</resources>\n'
        self.assertEqual(
            analyze.extract_string_names(text, r'(?<=<string name=")[^"]+'),
            {"app_name"},
        )

    def test_missing_keys_detected_like_the_ci_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            res = root / "android/app/src/main/res"
            (res / "values").mkdir(parents=True)
            (res / "values/strings.xml").write_text(
                '<string name="a">A</string><string name="b">B</string>'
            )
            (res / "values-it").mkdir()
            (res / "values-it/strings.xml").write_text('<string name="a">A</string>')  # b missing
            (res / "values-night").mkdir()  # qualifier-only dir: no strings.xml → ignored
            with mock.patch.object(analyze, "ANDROID_RES_DIR", res), mock.patch.object(
                analyze, "ANDROID_DEFAULT_STRINGS", res / "values/strings.xml"
            ):
                facts = analyze.strings_facts()
            self.assertEqual(facts["android_locales"], {"it": ["a"]})
            self.assertEqual(facts["missing"], {"it": ["b"]})

    def test_real_repo_is_complete(self):
        facts = analyze.strings_facts()
        self.assertEqual(facts["missing"], {})
        self.assertEqual(
            set(facts["android_locales"]),
            {"ar", "de", "es", "fr", "hi", "it", "ko", "pt", "ru", "zh"},
        )
        self.assertEqual(
            facts["web_locales"],
            ["ar", "de", "en", "es", "fr", "hi", "it", "ko", "pt", "ru", "zh"],
        )

    def test_registry_locale_declaration_must_match_discovered_sets(self):
        registry = load_real_registry()
        facts = analyze.strings_facts()
        self.assertEqual(analyze.check_strings(registry, facts), [])
        # A lying declaration must fail.
        bad = json.loads(json.dumps(registry))  # deep copy via json (registry is plain)
        for contract in bad["contracts"]:
            if "locales" in contract:
                contract["locales"] = contract["locales"][:-1]
        errors = analyze.check_strings(bad, facts)
        self.assertTrue(any("declares locales" in e for e in errors), errors)

    def test_missing_android_keys_fail_the_cross_check(self):
        registry = load_real_registry()
        facts = analyze.strings_facts()
        facts["missing"] = {"ko": ["app_name"]}
        errors = analyze.check_strings(registry, facts)
        self.assertTrue(any("'ko' is missing" in e for e in errors), errors)


class SchemaValidationTest(unittest.TestCase):
    """Unit checks against synthetic (broken) registries."""

    def _minimal(self) -> dict:
        return {
            "schema_version": 1,
            "updated": "2026-11-08",
            "clients": {
                "api": {
                    "kind": "backend",
                    "repo_path": "api/",
                    "description": "backend",
                },
                "web": {
                    "kind": "client",
                    "repo_path": "frontend/",
                    "description": "web",
                },
                "android": {
                    "kind": "client",
                    "repo_path": "android/",
                    "description": "android",
                },
                "ios": {
                    "kind": "client",
                    "repo_path": "ios/",
                    "status": "planned",
                    "story": "BITB-087",
                    "description": "ios",
                },
            },
            "contracts": [
                {
                    "id": "demo-contract",
                    "description": "demo",
                    "source_of_truth": ["api/chat/service.py"],
                    "consumers": {
                        "web": {
                            "status": "synced",
                            "evidence": "frontend/src/lib/api.ts",
                        }
                    },
                }
            ],
            "capabilities": [
                {
                    "id": "demo-cap",
                    "title": "Demo",
                    "description": "demo",
                    "parity": {
                        "api": {"status": "n/a"},
                        "web": {
                            "status": "synced",
                            "evidence": "frontend/src/lib/api.ts",
                        },
                        "android": {"status": "absent"},
                        "ios": {"status": "obligated", "story": "BITB-087"},
                    },
                }
            ],
        }

    def test_minimal_registry_is_valid(self):
        self.assertEqual(analyze.validate_schema(self._minimal()), [])

    def test_unknown_status_rejected(self):
        registry = self._minimal()
        registry["capabilities"][0]["parity"]["web"]["status"] = "ship-it"
        errors = analyze.validate_schema(registry)
        self.assertTrue(any("ship-it" in e for e in errors), errors)

    def test_synced_requires_evidence(self):
        registry = self._minimal()
        del registry["capabilities"][0]["parity"]["web"]["evidence"]
        errors = analyze.validate_schema(registry)
        self.assertTrue(any("evidence" in e for e in errors), errors)

    def test_obligated_requires_story(self):
        registry = self._minimal()
        del registry["capabilities"][0]["parity"]["ios"]["story"]
        errors = analyze.validate_schema(registry)
        self.assertTrue(any("story" in e for e in errors), errors)

    def test_parity_must_cover_all_four_clients(self):
        registry = self._minimal()
        del registry["capabilities"][0]["parity"]["android"]
        errors = analyze.validate_schema(registry)
        self.assertTrue(any("android" in e for e in errors), errors)

    def test_gap_ids_and_story_refs_patterned(self):
        registry = self._minimal()
        registry["capabilities"][0]["origin"] = {
            "source": "wip-plan",
            "gaps": ["GAP-99"],
        }
        errors = analyze.validate_schema(registry)
        self.assertTrue(any("GAP-99" in e for e in errors), errors)


class CrossReferenceTest(unittest.TestCase):
    def test_unknown_contract_reference(self):
        registry = {
            "contracts": [{"id": "a"}],
            "capabilities": [{"id": "x", "contracts": ["b"]}],
        }
        errors = analyze.check_cross_references(registry)
        self.assertTrue(any("unknown contract 'b'" in e for e in errors), errors)

    def test_duplicate_ids(self):
        registry = {
            "contracts": [{"id": "a"}, {"id": "a"}],
            "capabilities": [{"id": "x"}, {"id": "x"}],
        }
        errors = analyze.check_cross_references(registry)
        self.assertEqual(len([e for e in errors if "duplicate" in e]), 2)


class EvidencePathTest(unittest.TestCase):
    def test_missing_evidence_path_fails(self):
        registry = {
            "contracts": [],
            "capabilities": [
                {
                    "id": "x",
                    "parity": {
                        "web": {
                            "status": "synced",
                            "evidence": "frontend/src/lib/nope.ts",
                        }
                    },
                }
            ],
        }
        errors = analyze.check_evidence_paths(registry)
        self.assertEqual(len(errors), 1)
        self.assertIn("nope.ts", errors[0])

    def test_path_with_line_suffix_checked_without_suffix(self):
        registry = {
            "contracts": [],
            "capabilities": [
                {
                    "id": "x",
                    "parity": {
                        "web": {
                            "status": "synced",
                            "evidence": "frontend/src/lib/api.ts:699",
                        }
                    },
                }
            ],
        }
        self.assertEqual(analyze.check_evidence_paths(registry), [])

    def test_non_path_evidence_untouched(self):
        registry = {
            "contracts": [],
            "capabilities": [
                {
                    "id": "x",
                    "parity": {"web": {"status": "synced", "evidence": "PR #685"}},
                }
            ],
        }
        self.assertEqual(analyze.check_evidence_paths(registry), [])


class GraphDeterminismTest(unittest.TestCase):
    def test_two_runs_byte_identical(self):
        registry = load_real_registry()
        facts = analyze.strings_facts()
        first = analyze.render_graph_json(analyze.build_graph(registry, facts))
        second = analyze.render_graph_json(analyze.build_graph(registry, facts))
        self.assertEqual(first, second)

    def test_json_is_sorted(self):
        graph = analyze.build_graph(load_real_registry(), analyze.strings_facts())
        text = analyze.render_graph_json(graph)
        self.assertEqual(json.loads(text), graph)  # round-trips
        # sort_keys ⇒ first-level keys appear in sorted order in the text.
        top_keys = [line.split('"')[1] for line in text.splitlines() if line.startswith('  "')]
        self.assertEqual(top_keys, sorted(top_keys))


class CliTest(unittest.TestCase):
    def test_check_passes_on_fresh_tree(self):
        self.assertEqual(analyze.main(["--check"]), 0)

    def test_check_fails_on_stale_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "graph.json"
            stale.write_text("{}\n")
            with mock.patch.object(analyze, "GRAPH_PATH", stale):
                self.assertEqual(analyze.main(["--check"]), 1)

    def test_write_emits_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "graph.json"
            with mock.patch.object(analyze, "GRAPH_PATH", out):
                self.assertEqual(analyze.main([]), 0)
                graph = json.loads(out.read_text(encoding="utf-8"))
                self.assertEqual(graph["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
