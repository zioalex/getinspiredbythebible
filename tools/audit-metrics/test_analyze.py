#!/usr/bin/env python3
"""Tests for the audit-report parser — the machine check on audit tallies.

Stdlib unittest so it runs with bare `python3` (no pytest/venv needed):

    python3 tools/audit-metrics/test_analyze.py

Also collected by pytest. The audit-metrics workflow runs this before it
trusts analyze.py to snapshot a report, so template drift fails loud in CI
instead of silently miscounting the trend.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402


def parse(body: str) -> dict:
    """Write `body` to a correctly-named report file and parse it."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "2026-09-adversarial-audit.md"
        p.write_text(body, encoding="utf-8")
        return analyze.parse_report(p)


NORMAL = """# Audit

### A1 — A monolith
- **[SEVERITY]:** CRITICAL
- **[STATUS]:** NEW

### S2 — A slow query
- **[SEVERITY]:** HIGH
- **[STATUS]:** STILL OPEN

### D3 — A resolved gap
- **[SEVERITY]:** MEDIUM
- **[STATUS]:** RESOLVED
"""


class ParseReportTest(unittest.TestCase):
    def test_open_tallies_by_severity_and_category(self):
        m = parse(NORMAL)
        self.assertEqual(m["open_total"], 2)
        self.assertEqual(m["open_by_severity"]["CRITICAL"], 1)
        self.assertEqual(m["open_by_severity"]["HIGH"], 1)
        self.assertEqual(m["open_by_severity"]["MEDIUM"], 0)  # the MEDIUM is resolved
        self.assertEqual(m["open_by_category"]["architectural_debt"], 1)
        self.assertEqual(m["open_by_category"]["scalability_bottlenecks"], 1)
        self.assertEqual(m["open_ids"], ["A1", "S2"])

    def test_resolved_excluded_from_open(self):
        m = parse(NORMAL)
        self.assertEqual(m["resolved_ids"], ["D3"])
        self.assertNotIn("D3", m["open_ids"])

    def test_risk_score_weighting(self):
        # CRITICAL(10) + HIGH(5); the resolved MEDIUM does not count.
        self.assertEqual(parse(NORMAL)["risk_score"], 15)

    def test_baseline_style_without_status_lines(self):
        # The first report predates the [STATUS] convention: no status line,
        # every finding still counts as open.
        m = parse(
            "### A1 — X\n- **[SEVERITY]:** LOW\n\n### O2 — Y\n- **[SEVERITY]:** HIGH\n"
        )
        self.assertEqual(m["open_total"], 2)
        self.assertEqual(m["risk_score"], 6)  # LOW(1) + HIGH(5)

    def test_missing_severity_raises(self):
        # Heading present, no [SEVERITY], not RESOLVED → template drift, fail loud.
        with self.assertRaises(ValueError) as ctx:
            parse("### A1 — Broken finding\n- **[RISK PROFILE]:** Security\n")
        self.assertIn("A1", str(ctx.exception))

    def test_resolved_without_severity_is_fine(self):
        # A resolved recap legitimately need not carry a severity line.
        m = parse("### A1 — Was bad\n- **[STATUS]:** RESOLVED\n")
        self.assertEqual(m["resolved_ids"], ["A1"])
        self.assertEqual(m["open_total"], 0)

    def test_non_finding_headings_ignored(self):
        # Section headers like "### Turnstile" don't match the ID pattern.
        m = parse("## 1. ARCH\n### Turnstile\nsome prose\n### A1 — Real\n- **[SEVERITY]:** LOW\n")
        self.assertEqual(m["open_ids"], ["A1"])


if __name__ == "__main__":
    unittest.main()
