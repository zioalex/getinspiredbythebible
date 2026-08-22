#!/usr/bin/env python3
"""Generate the Android and web localized book-name maps from the canonical JSON (BITB-059).

``tests/fixtures/localized_book_map.json`` is the single source of truth for the
localized-book-name -> canonical-English-book-name map. This script regenerates:

  - ``android/app/src/main/kotlin/org/voxquieta/app/utils/LocalizedBookToEnglish.kt``
  - ``frontend/src/lib/localizedBookMap.generated.ts``

from it. Never hand-edit either generated file: edit the JSON, then run this script.

    python scripts/generate_localized_book_map.py

--check   Regenerate both targets in memory and diff against the committed files. Exits 1
          (and prints a diff for each mismatch) if any differ — i.e. a generated file was
          hand-edited, or the JSON changed without regenerating. Safe for CI; makes no
          changes on disk.

Phase 1 (BITB-059) covered the Android artifact. Phase 2 adds the web artifact. The
backend's own map (``api/utils/translation_registry.py``) is a separate master — it carries
per-translation-code, case-preserving data the flat lowercase JSON cannot represent — and is
held contradiction-free with this JSON by
``api/tests/test_localized_book_map_registry_parity.py`` rather than generation. See the
BITB-059 story for what Phase 3 (the regex grammar) still defers.
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
_TS_PATH = _REPO_ROOT / "frontend" / "src" / "lib" / "localizedBookMap.generated.ts"

_KT_HEADER = """package org.voxquieta.app.utils

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

_KT_FOOTER = ")\n"

_TS_HEADER = """/**
 * Bundled fallback map of localized Bible book names (lowercased) to their canonical
 * English book names (lowercased).
 *
 * Canonical source: tests/fixtures/localized_book_map.json (BITB-059). The Android copy
 * (android/.../utils/LocalizedBookToEnglish.kt) is generated from the same file. The
 * backend's own map (api/utils/translation_registry.py) is a separate master, held
 * contradiction-free by api/tests/test_localized_book_map_registry_parity.py.
 *
 * Runtime API data from /api/v1/scripture/book-names is merged on top of — never
 * replaces — this map, via updateBookNames() in verseExtraction.ts.
 *
 * @generated from tests/fixtures/localized_book_map.json by
 * scripts/generate_localized_book_map.py — DO NOT EDIT individual entries by hand. Edit
 * the JSON and re-run the generator.
 */
// prettier-ignore
export const LOCALIZED_BOOK_TO_ENGLISH: Record<string, string> = {
"""

_TS_FOOTER = "};\n"


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
    lines = [_KT_HEADER]
    for key, value in book_map.items():
        lines.append(f"    {_kt_string_literal(key)} to {_kt_string_literal(value)},\n")
    lines.append(_KT_FOOTER)
    return "".join(lines)


def _ts_string_literal(value: str) -> str:
    # json.dumps produces a valid TS/JS string literal for every key/value in the map;
    # ensure_ascii=False keeps the non-Latin book names human-readable in the source.
    return json.dumps(value, ensure_ascii=False)


def render_typescript(book_map: dict[str, str]) -> str:
    lines = [_TS_HEADER]
    for key, value in book_map.items():
        lines.append(f"  {_ts_string_literal(key)}: {_ts_string_literal(value)},\n")
    lines.append(_TS_FOOTER)
    return "".join(lines)


# (output path, renderer, human label) — add a new target here for a future platform.
_TARGETS = [
    (_KT_PATH, render_kotlin, "LocalizedBookToEnglish.kt"),
    (_TS_PATH, render_typescript, "localizedBookMap.generated.ts"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed generated files match the JSON; do not write anything.",
    )
    args = parser.parse_args()

    book_map = _load_book_map()

    if args.check:
        failed = False
        for path, render, label in _TARGETS:
            generated = render(book_map)
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != generated:
                failed = True
                diff = difflib.unified_diff(
                    current.splitlines(keepends=True),
                    generated.splitlines(keepends=True),
                    fromfile=str(path.relative_to(_REPO_ROOT)),
                    tofile="generated",
                )
                print(
                    f"FAIL: {label} is out of sync with "
                    "tests/fixtures/localized_book_map.json.\n"
                    "Run `python scripts/generate_localized_book_map.py` and commit the result.\n",
                    file=sys.stderr,
                )
                sys.stderr.writelines(diff)
            else:
                print(f"OK: {label} matches tests/fixtures/localized_book_map.json.")
        return 1 if failed else 0

    for path, render, label in _TARGETS:
        generated = render(book_map)
        path.write_text(generated, encoding="utf-8")
        print(f"Wrote {len(book_map)} entries to {path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
