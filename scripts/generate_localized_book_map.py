#!/usr/bin/env python3
"""Generate the Android bundled localized book-name map from the canonical JSON (BITB-059).

``tests/fixtures/localized_book_map.json`` is the single source of truth for the
localized-book-name -> canonical-English-book-name map. This script regenerates
``android/app/src/main/kotlin/org/voxquieta/app/utils/LocalizedBookToEnglish.kt`` from it.

Never hand-edit the generated .kt file: edit the JSON, then run this script.

    python scripts/generate_localized_book_map.py

--check   Regenerate in memory and diff against the committed .kt file. Exits 1 (and prints
          a diff) if they differ — i.e. the .kt file was hand-edited or the JSON changed
          without regenerating. Safe for CI; makes no changes on disk.

Phase 1 (BITB-059) covers only the Android artifact. The web map
(frontend/src/lib/verseExtraction.ts) stays hand-written for now, locked to this JSON by a
parity test (frontend/src/lib/localizedBookMap.parity.test.ts) rather than generation — see
the BITB-059 story's Scope Note for what Phase 2 defers.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_JSON_PATH = _REPO_ROOT / "tests" / "fixtures" / "localized_book_map.json"
_KT_PATH = (
    _REPO_ROOT
    / "android"
    / "app"
    / "src"
    / "main"
    / "kotlin"
    / "org"
    / "voxquieta"
    / "app"
    / "utils"
    / "LocalizedBookToEnglish.kt"
)

_HEADER = """package org.voxquieta.app.utils

/**
 * Bundled fallback map of localized Bible book names (lowercased) to their canonical
 * English book names (lowercased).
 *
 * This is the Android copy of the canonical map at tests/fixtures/localized_book_map.json
 * (BITB-059), which in turn mirrors the backend source of truth
 * (api/utils/translation_registry.py). It lets verse detection and normalization work
 * offline / before the /api/v1/scripture/book-names call returns. Runtime API data is
 * merged on top of — never replaced by — this map.
 *
 * @generated from tests/fixtures/localized_book_map.json by
 * scripts/generate_localized_book_map.py — DO NOT EDIT individual entries by hand. Edit the
 * JSON and re-run the generator; LocalizedBookToEnglishTest checks content equivalence
 * against the JSON so drift fails CI.
 */
internal val LOCALIZED_BOOK_TO_ENGLISH: Map<String, String> = mapOf(
"""

_FOOTER = ")\n"


def _load_book_map() -> dict[str, str]:
    payload = json.loads(_JSON_PATH.read_text(encoding="utf-8"))
    return payload["book_map"]


def _kt_string_literal(value: str) -> str:
    # The book-name map never contains characters that need escaping beyond the
    # standard Kotlin string escapes; guard against surprises rather than silently
    # emitting invalid Kotlin.
    if '"' in value or "\\" in value or "\n" in value:
        raise ValueError(f"value requires escaping the generator does not support: {value!r}")
    return f'"{value}"'


def render_kotlin(book_map: dict[str, str]) -> str:
    lines = [_HEADER]
    for key, value in book_map.items():
        lines.append(f"    {_kt_string_literal(key)} to {_kt_string_literal(value)},\n")
    lines.append(_FOOTER)
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed .kt file matches the JSON; do not write anything.",
    )
    args = parser.parse_args()

    book_map = _load_book_map()
    generated = render_kotlin(book_map)

    if args.check:
        current = _KT_PATH.read_text(encoding="utf-8") if _KT_PATH.exists() else ""
        if current != generated:
            diff = difflib.unified_diff(
                current.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=str(_KT_PATH.relative_to(_REPO_ROOT)),
                tofile="generated",
            )
            print(
                "FAIL: LocalizedBookToEnglish.kt is out of sync with "
                "tests/fixtures/localized_book_map.json.\n"
                "Run `python scripts/generate_localized_book_map.py` and commit the result.\n",
                file=sys.stderr,
            )
            sys.stderr.writelines(diff)
            return 1
        print("OK: LocalizedBookToEnglish.kt matches tests/fixtures/localized_book_map.json.")
        return 0

    _KT_PATH.write_text(generated, encoding="utf-8")
    print(f"Wrote {len(book_map)} entries to {_KT_PATH.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
