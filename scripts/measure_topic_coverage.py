#!/usr/bin/env python3
"""Offline, network-only corpus scan for topic-tagging coverage (BITB-106).

``scripts/populate_verse_topics.py --dry-run --verbose`` answers the same
question but needs a live Postgres with the translation already loaded
(``DATABASE_URL``) and pulls in the full API dependency chain (pydantic-
settings, asyncpg, ...) because it imports ``chat.topic_tagging`` through the
``chat`` package. Neither is available in every environment that needs to
validate a language before relying on ``CORPUS_KEYWORD_DENYLIST`` staying
empty for it.

This script answers the identical question — "does any keyword/topic tag
more than the guideline share of a real corpus?" — using only the standard
library plus whatever HTTP access is available, against the *same* matching
code (``api/chat/topic_tagging.py`` / ``api/chat/topics.py``, loaded directly
by file path — see ``_load_tagging_module()`` — so this can never silently
drift from what the population script actually does).

Calibration: running ``--language en`` against the committed
``data/bible/kjv.json`` must reproduce BITB-044's published numbers
("guidance" ~3.2%, "anger" ~1.56%) almost exactly (small deltas are possible
if the keyword map has changed since). That equivalence is what makes this
script's output usable as evidence in place of a DB-backed dry run.

Usage:
    python3 scripts/measure_topic_coverage.py --language it
    python3 scripts/measure_topic_coverage.py --language ar --top-keywords 15 --json
    python3 scripts/measure_topic_coverage.py --all

Exit codes:
    0: no topic breached the coverage guideline
    1: at least one topic breached it (or the run failed outright)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import types
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import URLError

REPO_ROOT = Path(__file__).parent.parent
API_DIR = REPO_ROOT / "api"

_OSIS_NS = {"osis": "http://www.bibletechnologies.net/2003/OSIS/namespace"}


@dataclass(frozen=True)
class CorpusSource:
    """Where to read one language's verse text from, and how."""

    language: str
    translation_label: str
    format: str  # "thiagobodruk" | "osis"
    location: str  # local path (relative to repo root) or an https:// URL
    license_note: str


# Only the two in-repo languages need no network. The other five are read
# from public GitHub mirrors reachable over plain HTTPS — none of this text
# is committed to this repository; it is fetched fresh for measurement only.
KNOWN_CORPUS_SOURCES: dict[str, CorpusSource] = {
    "en": CorpusSource(
        "en", "KJV", "thiagobodruk", "data/bible/kjv.json", "Public domain (King James Version)."
    ),
    "de": CorpusSource(
        "de",
        "Luther 1912",
        "thiagobodruk",
        "data/bible/translations/luther1912.json",
        "Public domain (Luther 1912).",
    ),
    "it": CorpusSource(
        "it",
        "Riveduta (OSIS)",
        "osis",
        "https://raw.githubusercontent.com/seven1m/open-bibles/master/ita-riveduta.osis.xml",
        "seven1m/open-bibles lists this Public Domain; the file's own OSIS "
        "header carries a 1990 SBBF copyright notice. Flagged, not resolved, "
        "by this script — do not commit this text to the repo before that is "
        "cleared. Also not the exact `ita1927` edition production would load.",
    ),
    "es": CorpusSource(
        "es",
        "Reina-Valera",
        "thiagobodruk",
        "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/es_rvr.json",
        "Public domain (Reina-Valera); matches production's `valera`.",
    ),
    "fr": CorpusSource(
        "fr",
        "fr_apee",
        "thiagobodruk",
        "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/fr_apee.json",
        "Public domain, but NOT the `ls1910` (Louis Segond 1910) edition "
        "production would load — that edition is only available via "
        "api.getbible.net, which this script cannot reach from every "
        "environment. Treat this as a reasonable stand-in, not a match.",
    ),
    "pt": CorpusSource(
        "pt",
        "Almeida Atualizada",
        "thiagobodruk",
        "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/pt_aa.json",
        "Matches production's `almeida`; confirm the specific Almeida "
        "edition's license before treating this as a redistribution source.",
    ),
    "ar": CorpusSource(
        "ar",
        "Smith & Van Dyke",
        "thiagobodruk",
        "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/ar_svd.json",
        "Public domain (Smith & Van Dyke); matches production's `arabicsv`.",
    ),
}


def _load_tagging_module():
    """Load ``api/chat/topic_tagging.py`` (and its ``api/chat/topics.py``
    dependency) without executing ``api/chat/__init__.py``.

    The real package init imports ``ChatService``, which pulls in
    pydantic-settings via ``config.settings`` — a chain this script has no
    need of and that may not even be installed (that is the whole point of
    keeping this script stdlib-only). ``utils.logging_config`` is stubbed for
    the same reason: ``chat.topics`` only wants a logger from it.
    """
    if "chat.topic_tagging" in sys.modules:
        return sys.modules["chat.topic_tagging"]

    if "utils.logging_config" not in sys.modules:
        utils_pkg = types.ModuleType("utils")
        utils_pkg.__path__ = []  # mark as a package without scanning api/utils
        logging_config_stub = types.ModuleType("utils.logging_config")
        logging_config_stub.get_logger = lambda name: __import__("logging").getLogger(name)
        sys.modules.setdefault("utils", utils_pkg)
        sys.modules["utils.logging_config"] = logging_config_stub

    if "chat" not in sys.modules:
        chat_pkg = types.ModuleType("chat")
        chat_pkg.__path__ = [str(API_DIR / "chat")]
        sys.modules["chat"] = chat_pkg

    def _load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    _load("chat.topics", API_DIR / "chat" / "topics.py")
    return _load("chat.topic_tagging", API_DIR / "chat" / "topic_tagging.py")


def _fetch(location: str) -> bytes:
    if location.startswith("http://") or location.startswith("https://"):
        with urllib.request.urlopen(location, timeout=30) as response:  # noqa: S310
            return response.read()
    return (REPO_ROOT / location).read_bytes()


def _read_thiagobodruk(raw: bytes) -> list[str]:
    data = json.loads(raw.decode("utf-8-sig"))
    verses: list[str] = []
    for book in data:
        for chapter in book["chapters"]:
            verses.extend(v for v in chapter if v)
    return verses


def _read_osis(raw: bytes) -> list[str]:
    root = ET.fromstring(raw)  # noqa: S314 - fixed, known-good source list above
    return [
        "".join(el.itertext())
        for el in root.findall(".//osis:verse", _OSIS_NS)
        if "".join(el.itertext()).strip()
    ]


def load_corpus(source: CorpusSource) -> list[str]:
    raw = _fetch(source.location)
    if source.format == "thiagobodruk":
        return _read_thiagobodruk(raw)
    if source.format == "osis":
        return _read_osis(raw)
    raise ValueError(f"unknown corpus format: {source.format}")


@dataclass
class CoverageReport:
    language: str
    verse_count: int
    tagged_count: int
    topic_counts: Counter[str] = field(default_factory=Counter)
    keyword_counts: dict[str, Counter[str]] = field(default_factory=dict)

    def topic_pct(self, topic: str) -> float:
        return (
            100.0 * self.topic_counts.get(topic, 0) / self.verse_count if self.verse_count else 0.0
        )

    def keyword_pct(self, topic: str, keyword: str) -> float:
        count = self.keyword_counts.get(topic, Counter()).get(keyword, 0)
        return 100.0 * count / self.verse_count if self.verse_count else 0.0


def measure_topic_coverage(
    texts: Iterable[str],
    language: str,
    tagging_module,
    *,
    denylist=None,
) -> CoverageReport:
    """Pure function: scan ``texts`` and count topic/keyword hits.

    Uses the real ``build_topic_matchers`` / ``build_keyword_matchers`` /
    ``match_topics`` / ``match_topic_keywords`` from ``api/chat/topic_tagging.py``
    (passed in as ``tagging_module``) — this scanner adds no matching logic
    of its own.
    """
    topic_matchers = tagging_module.build_topic_matchers(language, denylist=denylist)
    keyword_matchers = tagging_module.build_keyword_matchers(language, denylist=denylist)

    report = CoverageReport(language=language, verse_count=0, tagged_count=0)
    for text in texts:
        report.verse_count += 1
        topics = tagging_module.match_topics(text, language, topic_matchers)
        if topics:
            report.tagged_count += 1
            report.topic_counts.update(topics)
        keyword_hits = tagging_module.match_topic_keywords(text, language, keyword_matchers)
        for topic, keywords in keyword_hits.items():
            report.keyword_counts.setdefault(topic, Counter()).update(keywords)
    return report


def _print_report(
    report: CoverageReport, source: CorpusSource, guideline_pct: float, top_keywords: int
) -> bool:
    print(f"\n=== {report.language} ({source.translation_label}) ===")
    print(f"license note: {source.license_note}")
    print(f"verses scanned: {report.verse_count}")
    tagged_pct = 100.0 * report.tagged_count / report.verse_count if report.verse_count else 0.0
    print(f"verses tagged (any topic): {report.tagged_count} ({tagged_pct:.1f}%)")

    breached = False
    for topic, count in report.topic_counts.most_common():
        pct = report.topic_pct(topic)
        flag = "  <== exceeds guideline" if pct > guideline_pct else ""
        if pct > guideline_pct:
            breached = True
        print(f"  {topic}: {count} ({pct:.2f}%){flag}")
        if top_keywords:
            top = report.keyword_counts.get(topic, Counter()).most_common(top_keywords)
            for keyword, kw_count in top:
                print(f"      {keyword!r}: {kw_count} ({report.keyword_pct(topic, keyword):.2f}%)")
    return breached


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--language", action="append", dest="languages", help="Language code to scan (repeatable)."
    )
    parser.add_argument(
        "--all", action="store_true", help="Scan every language in KNOWN_CORPUS_SOURCES."
    )
    parser.add_argument(
        "--top-keywords", type=int, default=5, help="Per-topic keyword breakdown depth (0 to skip)."
    )
    parser.add_argument(
        "--guideline-pct",
        type=float,
        default=None,
        help="Override the coverage guideline (default: the module constant).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of text."
    )
    args = parser.parse_args(argv)

    languages = args.languages or (list(KNOWN_CORPUS_SOURCES) if args.all else [])
    if not languages:
        parser.error("pass --language <code> (repeatable) or --all")

    tagging = _load_tagging_module()
    guideline_pct = (
        args.guideline_pct if args.guideline_pct is not None else tagging.COVERAGE_GUIDELINE_PCT
    )

    results: dict[str, dict] = {}
    any_breach = False
    for language in languages:
        source = KNOWN_CORPUS_SOURCES.get(language)
        if source is None:
            print(
                f"::error::no corpus source configured for language {language!r}", file=sys.stderr
            )
            return 1
        try:
            texts = load_corpus(source)
        except (URLError, OSError) as exc:
            print(f"::error::could not fetch corpus for {language!r}: {exc}", file=sys.stderr)
            return 1

        report = measure_topic_coverage(texts, language, tagging)
        if args.json:
            results[language] = {
                "translation": source.translation_label,
                "verse_count": report.verse_count,
                "tagged_count": report.tagged_count,
                "topic_counts": dict(report.topic_counts),
                "keyword_counts": {t: dict(c) for t, c in report.keyword_counts.items()},
            }
        else:
            if _print_report(report, source, guideline_pct, args.top_keywords):
                any_breach = True

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        any_breach = any(
            100.0 * count / r["verse_count"] > guideline_pct
            for r in results.values()
            for count in r["topic_counts"].values()
        )

    return 1 if any_breach else 0


if __name__ == "__main__":
    sys.exit(main())
