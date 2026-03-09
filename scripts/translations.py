"""
Translation configurations and book name mappings for multilingual Bible support.

This module contains:
- Translation metadata (language, source URLs, etc.)
- Book name mappings (derived from api/utils/translation_registry.py)
- Data source configurations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADDING A NEW LANGUAGE — CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When adding a new language/translation, you must update ALL of the following
or the app will silently fall back to English for that language:

 1. api/utils/translation_registry.py  ← SINGLE SOURCE OF TRUTH FOR BOOK NAMES
    a. Add an ENGLISH_TO_<LANGUAGE> dict (English → localized, 66 books)
       Use the primary form that appears in the source feed as the value.
    b. If the feed uses alias forms (alternate grammar, BOM, no-space etc.),
       add them to EXTRA_REVERSE_MAPPINGS.
    c. Register the translation: add "my_code": ENGLISH_TO_MY_LANGUAGE
       to TRANSLATION_REGISTRY.
    → This automatically updates book_names.py, verse_parser.py, AND
      this file (scripts/translations.py) — no further edits needed there.

 2. scripts/translations.py  (THIS FILE)
    a. Add an entry to TRANSLATIONS dict with keys:
         code, name, language, language_code, description, source, url,
         book_names, license, is_default
       For book_names, use the auto-generated <LANGUAGE>_BOOK_NAMES variable
       defined below (it is derived from translation_registry.py).
    b. source must be one of: "getbible", "thiagobodruk", "scrollmapper", "manual"
    c. url=None is allowed ONLY when source="manual" (no free download source exists)

 3. scripts/init.sql
    Add an INSERT row for the translation so the DB is seeded on fresh deploy.
    Or regenerate via:
      python -c "from translations import generate_translations_sql; print(generate_translations_sql())"

 4. api/utils/language.py
    a. Add ISO code to SUPPORTED_LANGUAGES list
    b. Add entry to LANGUAGE_TRANSLATIONS dict  (e.g. "ru": ["synodal"])
    c. Add entry to TRANSLATION_INFO dict
    d. Add ENGLISH_TO_<LANGUAGE>_BOOKS dict — import from translation_registry.py
    e. Add to get_localized_book_name() book_map dict

 5. frontend/messages/<locale>.json
    Create the UI translation file for the new locale.

 6. frontend/src/i18n/routing.ts
    Add the locale code to the locales array.

 7. frontend/src/components/LanguageSwitcher.tsx
    Add the locale label.

 8. frontend/src/app/[locale]/layout.tsx
    Add an hreflang alternate entry.

 9. api/chat/prompts.py
    Add to LANGUAGE_NAMES and SOURCE_ATTRIBUTION_EXAMPLES.

10. Run all tests:
      cd api && pytest -m "not network" -q
    And check specifically:
      pytest tests/test_translations.py tests/test_multilingual_integration.py -q -m "not network"

11. Count check — update the assertion in:
      api/tests/test_translations.py::test_list_available_translations
    (change the expected count from N to N+1)

NOTES:
- getBible codes sometimes differ from internal codes.
  Always verify at: https://api.getbible.net/v2/<code>.json
  Internal code = what language.py uses; getBible code = what goes in the URL.
  Example: internal "cuv" → URL uses "cus"; internal "krv" → URL uses "korean".
- If no free source exists, use source="manual", url=None and document how to
  load the data manually.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import importlib
import sys
from pathlib import Path

# Allow importing translation_registry directly from api/utils when running
# as a standalone script or from tests.
# We add api/utils/ (not api/) to sys.path so that Python imports
# translation_registry.py as a plain module, avoiding the api/utils/__init__.py
# which has heavy API-only dependencies (httpx etc.) not installed in scripts env.
_API_UTILS_DIR = Path(__file__).parent.parent / "api" / "utils"
if str(_API_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(_API_UTILS_DIR))

# Ensure a single module instance is shared between the bare name
# ("translation_registry") and the fully-qualified package name
# ("utils.translation_registry").  When pytest runs both test_translations.py
# (which triggers this file and uses the bare name) and test_utils_coverage.py
# (which imports utils.book_names and uses the qualified name), whichever test
# file is *collected first* determines which copy lands in sys.modules first.
# We therefore sync both directions before doing any imports:
#   • If utils.translation_registry is already cached (test_utils_coverage.py
#     was collected first), reuse it under the bare name too.
#   • Otherwise, load the bare module and register it under the qualified name.
if "utils.translation_registry" in sys.modules:
    # Reuse the already-loaded qualified module; expose it under the bare name
    # so the `from translation_registry import …` below resolves to it.
    sys.modules.setdefault("translation_registry", sys.modules["utils.translation_registry"])
else:
    # Load via bare name, then register under the qualified name so that
    # any subsequent `from utils.translation_registry import …` reuses it.
    _registry_module = importlib.import_module("translation_registry")
    sys.modules.setdefault("utils.translation_registry", _registry_module)

from translation_registry import (  # noqa: E402
    ENGLISH_TO_ARABIC,
    ENGLISH_TO_CHINESE,
    ENGLISH_TO_FRENCH,
    ENGLISH_TO_GERMAN,
    ENGLISH_TO_HINDI,
    ENGLISH_TO_ITALIAN,
    ENGLISH_TO_KOREAN,
    ENGLISH_TO_PORTUGUESE,
    ENGLISH_TO_RUSSIAN,
    ENGLISH_TO_SPANISH,
    EXTRA_REVERSE_MAPPINGS,
)

# ---------------------------------------------------------------------------
# localized → English  dicts used by load_bible.py and map_book_name()
# Derived automatically — no manual maintenance needed.
# ---------------------------------------------------------------------------

ITALIAN_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_ITALIAN.items()}

# German — canonical forms + Schlachter orthography alternates (Rut, Ester, Hohes Lied, Zefanja)
_GERMAN_ALTERNATES = {"Rut", "Ester", "Hohes Lied", "Zefanja"}
GERMAN_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_GERMAN.items()}
GERMAN_BOOK_NAMES.update(
    {alias: eng for alias, eng in EXTRA_REVERSE_MAPPINGS.items() if alias in _GERMAN_ALTERNATES}
)

SPANISH_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_SPANISH.items()}
FRENCH_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_FRENCH.items()}
PORTUGUESE_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_PORTUGUESE.items()}
ARABIC_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_ARABIC.items()}
HINDI_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_HINDI.items()}

# Russian — canonical forms + aliases (genitive/dative ordinal variants)
RUSSIAN_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_RUSSIAN.items()}
RUSSIAN_BOOK_NAMES.update(
    {
        alias: eng
        for alias, eng in EXTRA_REVERSE_MAPPINGS.items()
        if alias[0] in "БбВвГгДдЕеЁёЖжЗзИиЙйКкЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЪъЫыЬьЭэЮюЯя"
    }
)

# Chinese — canonical forms + BOM variant + Simplified Revelation alias
CHINESE_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_CHINESE.items()}
CHINESE_BOOK_NAMES.update(
    {
        alias: eng
        for alias, eng in EXTRA_REVERSE_MAPPINGS.items()
        if any(
            # CJK Unified Ideographs (main + Extension A + Compatibility)
            (0x4E00 <= ord(c) <= 0x9FFF)
            or (0x3400 <= ord(c) <= 0x4DBF)
            or (0xF900 <= ord(c) <= 0xFAFF)
            or c == "\ufeff"  # BOM prefix used in some getbible feeds
            for c in alias
        )
    }
)

# Korean — canonical forms + no-space Lamentations alias
KOREAN_BOOK_NAMES: dict[str, str] = {v: k for k, v in ENGLISH_TO_KOREAN.items()}
KOREAN_BOOK_NAMES.update(
    {
        alias: eng
        for alias, eng in EXTRA_REVERSE_MAPPINGS.items()
        if any(0xAC00 <= ord(c) <= 0xD7A3 for c in alias)
    }
)

# Deuterocanonical / apocryphal book names present in the Synodal feed
# (api.getbible.net/v2/synodal.json) that are NOT part of the 66-book
# Protestant canon and therefore have no entry in our database.
# The loader uses this set to emit an informational skip message instead
# of a misleading ⚠️ Unknown book warning.
DEUTEROCANONICAL_BOOK_NAMES: set[str] = {
    "Молитва Манассии",  # Prayer of Manasseh
    "1-я Ездры",  # 1 Esdras
    "2-я Ездры",  # 2 Esdras
    "Товит",  # Tobit
    "Юдифь",  # Judith
    "Премудрость Соломона",  # Wisdom of Solomon
    "Сирах",  # Sirach / Ecclesiasticus
    "Варух",  # Baruch
    "Epistle of Jeremiah",  # Epistle of Jeremiah
    "1-я Маккавеев",  # 1 Maccabees
    "2-я Маккавеев",  # 2 Maccabees
    "3-я Маккавеев",  # 3 Maccabees
}

# Translation configurations
TRANSLATIONS = {
    "kjv": {
        "code": "kjv",
        "name": "King James Version",
        "language": "English",
        "language_code": "en",
        "description": "Classic English translation from 1611",
        "source": "thiagobodruk",
        "url": "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/en_kjv.json",
        "book_names": None,  # Uses standard English names
        "license": "Public Domain",
        "is_default": True,
    },
    "web": {
        "code": "web",
        "name": "World English Bible",
        "language": "English",
        "language_code": "en",
        "description": "Modern English, public domain",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/web.json",
        "book_names": None,  # Uses standard English names
        "license": "Public Domain",
        "is_default": False,
    },
    "ita1927": {
        "code": "ita1927",
        "name": "Riveduta 1927",
        "language": "Italian",
        "language_code": "it",
        "description": "Italian Luzzi translation from 1927",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/riveduta.json",
        "book_names": ITALIAN_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
    "schlachter": {
        "code": "schlachter",
        "name": "Schlachter 1951",
        "language": "German",
        "language_code": "de",
        "description": "German Schlachter translation from 1951",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/schlachter.json",
        "book_names": GERMAN_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
    "valera": {
        "code": "valera",
        "name": "Reina Valera 1909",
        "language": "Spanish",
        "language_code": "es",
        "description": "Spanish Reina Valera translation from 1909",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/valera.json",
        "book_names": SPANISH_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
    "ls1910": {
        "code": "ls1910",
        "name": "Louis Segond 1910",
        "language": "French",
        "language_code": "fr",
        "description": "French Louis Segond translation from 1910",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/ls1910.json",
        "book_names": FRENCH_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
    "almeida": {
        "code": "almeida",
        "name": "Almeida Atualizada",
        "language": "Portuguese",
        "language_code": "pt",
        "description": "Portuguese Almeida Atualizada translation",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/almeida.json",
        "book_names": PORTUGUESE_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
    "arabicsv": {
        "code": "arabicsv",
        "name": "Smith & Van Dyke",
        "language": "Arabic",
        "language_code": "ar",
        "description": "Arabic Smith and Van Dyke translation",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/arabicsv.json",
        "book_names": ARABIC_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
    "synodal": {
        "code": "synodal",
        "name": "Синодальный перевод",
        "language": "Russian",
        "language_code": "ru",
        "description": "Russian Synodal Translation (1876)",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/synodal.json",
        "book_names": RUSSIAN_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
    "cuv": {
        "code": "cuv",
        "name": "中文和合本",
        "language": "Chinese",
        "language_code": "zh",
        "description": "Chinese Union Version (Simplified)",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/cus.json",
        "book_names": CHINESE_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
    "hindi": {
        "code": "hindi",
        "name": "Hindi IRV Bible",
        "language": "Hindi",
        "language_code": "hi",
        "description": "Hindi IRV Bible (Indian Revised Version)",
        "source": "manual",
        "url": None,
        "book_names": HINDI_BOOK_NAMES,
        "license": "Copyright IRV",
        "is_default": False,
    },
    "krv": {
        "code": "krv",
        "name": "개역개정",
        "language": "Korean",
        "language_code": "ko",
        "description": "Korean Revised Version",
        "source": "getbible",
        "url": "https://api.getbible.net/v2/korean.json",
        "book_names": KOREAN_BOOK_NAMES,
        "license": "Public Domain",
        "is_default": False,
    },
}


def generate_translations_sql() -> str:
    """
    Generate SQL INSERT statements for the translations table.

    This ensures init.sql stays in sync with TRANSLATIONS config.
    Usage: python -c "from translations import generate_translations_sql; print(generate_translations_sql())"
    """
    lines = [
        "-- Auto-generated from scripts/translations.py",
        '-- Run: python -c "from translations import generate_translations_sql; print(generate_translations_sql())"',
        "INSERT INTO translations (code, name, language, language_code, is_default, description) VALUES",
    ]

    values = []
    for code, config in TRANSLATIONS.items():
        is_default = "TRUE" if config.get("is_default", False) else "FALSE"
        # Escape single quotes in description
        description = config.get("description", "").replace("'", "''")
        values.append(
            f"    ('{code}', '{config['name']}', '{config['language']}', "
            f"'{config['language_code']}', {is_default}, '{description}')"
        )

    lines.append(",\n".join(values))
    lines.append("ON CONFLICT (code) DO NOTHING;")

    return "\n".join(lines)


def get_translation_config(code: str) -> dict:
    """Get configuration for a specific translation."""
    if code not in TRANSLATIONS:
        raise ValueError(f"Unknown translation code: {code}")
    return TRANSLATIONS[code]


def list_available_translations() -> list[dict]:
    """List all available translations."""
    return [
        {
            "code": t["code"],
            "name": t["name"],
            "language": t["language"],
            "language_code": t["language_code"],
        }
        for t in TRANSLATIONS.values()
    ]


def map_book_name(book_name: str, translation_code: str) -> str:
    """
    Map a localized book name to standard English name.

    Args:
        book_name: Book name in local language (e.g., "Genesi", "Matthäus")
        translation_code: Translation code (e.g., "ita1927", "deu1912")

    Returns:
        Standard English book name (e.g., "Genesis", "Matthew")
    """
    config = get_translation_config(translation_code)
    book_names = config.get("book_names")

    if book_names is None:
        # English translations use standard names
        return book_name

    # Look up in mapping
    return book_names.get(book_name, book_name)


def get_localized_book_name(english_name: str, translation_code: str) -> str:
    """
    Get the localized book name for a given English book name.

    Args:
        english_name: Standard English book name (e.g., "Genesis", "Psalms")
        translation_code: Translation code (e.g., "ita1927", "schlachter")

    Returns:
        Localized book name (e.g., "Genesi", "Psalmen") or English name if no mapping
    """
    config = get_translation_config(translation_code)
    book_names = config.get("book_names")

    if book_names is None:
        # English translations use standard names
        return english_name

    # Create reverse mapping (English -> Local)
    # Use first match only (ignore alternate spellings)
    reverse_map = {}
    for local_name, eng_name in book_names.items():
        if eng_name not in reverse_map:
            reverse_map[eng_name] = local_name

    return reverse_map.get(english_name, english_name)
