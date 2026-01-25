"""
Translation configurations and book name mappings for multilingual Bible support.

This module contains:
- Translation metadata (language, source URLs, etc.)
- Book name mappings (Italian/German → English)
- Data source configurations
"""

# Italian book names (Riveduta 1927) → Standard English names
ITALIAN_BOOK_NAMES = {
    # Old Testament
    "Genesi": "Genesis",
    "Esodo": "Exodus",
    "Levitico": "Leviticus",
    "Numeri": "Numbers",
    "Deuteronomio": "Deuteronomy",
    "Giosuè": "Joshua",
    "Giudici": "Judges",
    "Rut": "Ruth",
    "1 Samuele": "1 Samuel",
    "2 Samuele": "2 Samuel",
    "1 Re": "1 Kings",
    "2 Re": "2 Kings",
    "1 Cronache": "1 Chronicles",
    "2 Cronache": "2 Chronicles",
    "Esdra": "Ezra",
    "Neemia": "Nehemiah",
    "Ester": "Esther",
    "Giobbe": "Job",
    "Salmi": "Psalms",
    "Proverbi": "Proverbs",
    "Ecclesiaste": "Ecclesiastes",
    "Cantico dei Cantici": "Song of Solomon",
    "Isaia": "Isaiah",
    "Geremia": "Jeremiah",
    "Lamentazioni": "Lamentations",
    "Ezechiele": "Ezekiel",
    "Daniele": "Daniel",
    "Osea": "Hosea",
    "Gioele": "Joel",
    "Amos": "Amos",
    "Abdia": "Obadiah",
    "Giona": "Jonah",
    "Michea": "Micah",
    "Naum": "Nahum",
    "Abacuc": "Habakkuk",
    "Sofonia": "Zephaniah",
    "Aggeo": "Haggai",
    "Zaccaria": "Zechariah",
    "Malachia": "Malachi",
    # New Testament
    "Matteo": "Matthew",
    "Marco": "Mark",
    "Luca": "Luke",
    "Giovanni": "John",
    "Atti": "Acts",
    "Romani": "Romans",
    "1 Corinzi": "1 Corinthians",
    "2 Corinzi": "2 Corinthians",
    "Galati": "Galatians",
    "Efesini": "Ephesians",
    "Filippesi": "Philippians",
    "Colossesi": "Colossians",
    "1 Tessalonicesi": "1 Thessalonians",
    "2 Tessalonicesi": "2 Thessalonians",
    "1 Timoteo": "1 Timothy",
    "2 Timoteo": "2 Timothy",
    "Tito": "Titus",
    "Filemone": "Philemon",
    "Ebrei": "Hebrews",
    "Giacomo": "James",
    "1 Pietro": "1 Peter",
    "2 Pietro": "2 Peter",
    "1 Giovanni": "1 John",
    "2 Giovanni": "2 John",
    "3 Giovanni": "3 John",
    "Giuda": "Jude",
    "Apocalisse": "Revelation",
}

# German book names (Luther 1912 / Schlachter) → Standard English names
GERMAN_BOOK_NAMES = {
    # Old Testament
    "1. Mose": "Genesis",
    "2. Mose": "Exodus",
    "3. Mose": "Leviticus",
    "4. Mose": "Numbers",
    "5. Mose": "Deuteronomy",
    "Josua": "Joshua",
    "Richter": "Judges",
    "Ruth": "Ruth",
    "Rut": "Ruth",  # Alternate spelling (Schlachter)
    "1. Samuel": "1 Samuel",
    "2. Samuel": "2 Samuel",
    "1. Könige": "1 Kings",
    "2. Könige": "2 Kings",
    "1. Chronik": "1 Chronicles",
    "2. Chronik": "2 Chronicles",
    "Esra": "Ezra",
    "Nehemia": "Nehemiah",
    "Esther": "Esther",
    "Ester": "Esther",  # Alternate spelling (Schlachter)
    "Hiob": "Job",
    "Psalmen": "Psalms",
    "Sprüche": "Proverbs",
    "Prediger": "Ecclesiastes",
    "Hohelied": "Song of Solomon",
    "Hohes Lied": "Song of Solomon",  # Alternate spelling (Schlachter)
    "Jesaja": "Isaiah",
    "Jeremia": "Jeremiah",
    "Klagelieder": "Lamentations",
    "Hesekiel": "Ezekiel",
    "Daniel": "Daniel",
    "Hosea": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obadja": "Obadiah",
    "Jona": "Jonah",
    "Micha": "Micah",
    "Nahum": "Nahum",
    "Habakuk": "Habakkuk",
    "Zephanja": "Zephaniah",
    "Zefanja": "Zephaniah",  # Alternate spelling (Schlachter)
    "Haggai": "Haggai",
    "Sacharja": "Zechariah",
    "Maleachi": "Malachi",
    # New Testament
    "Matthäus": "Matthew",
    "Markus": "Mark",
    "Lukas": "Luke",
    "Johannes": "John",
    "Apostelgeschichte": "Acts",
    "Römer": "Romans",
    "1. Korinther": "1 Corinthians",
    "2. Korinther": "2 Corinthians",
    "Galater": "Galatians",
    "Epheser": "Ephesians",
    "Philipper": "Philippians",
    "Kolosser": "Colossians",
    "1. Thessalonicher": "1 Thessalonians",
    "2. Thessalonicher": "2 Thessalonians",
    "1. Timotheus": "1 Timothy",
    "2. Timotheus": "2 Timothy",
    "Titus": "Titus",
    "Philemon": "Philemon",
    "Hebräer": "Hebrews",
    "Jakobus": "James",
    "1. Petrus": "1 Peter",
    "2. Petrus": "2 Peter",
    "1. Johannes": "1 John",
    "2. Johannes": "2 John",
    "3. Johannes": "3 John",
    "Judas": "Jude",
    "Offenbarung": "Revelation",
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
}


def generate_translations_sql() -> str:
    """
    Generate SQL INSERT statements for the translations table.

    This ensures init.sql stays in sync with TRANSLATIONS config.
    Usage: python -c "from translations import generate_translations_sql; print(generate_translations_sql())"
    """
    lines = [
        "-- Auto-generated from scripts/translations.py",
        "-- Run: python -c \"from translations import generate_translations_sql; print(generate_translations_sql())\"",
        "INSERT INTO translations (code, name, language, language_code, is_default, description) VALUES"
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
