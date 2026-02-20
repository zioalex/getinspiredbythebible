"""
Translation configurations and book name mappings for multilingual Bible support.

This module contains:
- Translation metadata (language, source URLs, etc.)
- Book name mappings (Italian/German/Spanish/French/Portuguese/Arabic → English)
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

# Spanish book names (Reina Valera 1909) → Standard English names
SPANISH_BOOK_NAMES = {
    # Old Testament
    "Génesis": "Genesis",
    "Éxodo": "Exodus",
    "Levítico": "Leviticus",
    "Números": "Numbers",
    "Deuteronomio": "Deuteronomy",
    "Josué": "Joshua",
    "Jueces": "Judges",
    "Rut": "Ruth",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Reyes": "1 Kings",
    "2 Reyes": "2 Kings",
    "1 Crónicas": "1 Chronicles",
    "2 Crónicas": "2 Chronicles",
    "Esdras": "Ezra",
    "Nehemías": "Nehemiah",
    "Ester": "Esther",
    "Job": "Job",
    "Salmos": "Psalms",
    "Proverbios": "Proverbs",
    "Eclesiastés": "Ecclesiastes",
    "Cantares": "Song of Solomon",
    "Isaías": "Isaiah",
    "Jeremías": "Jeremiah",
    "Lamentaciones": "Lamentations",
    "Ezequiel": "Ezekiel",
    "Daniel": "Daniel",
    "Oseas": "Hosea",
    "Joel": "Joel",
    "Amós": "Amos",
    "Abdías": "Obadiah",
    "Jonás": "Jonah",
    "Miqueas": "Micah",
    "Nahúm": "Nahum",
    "Habacuc": "Habakkuk",
    "Sofonías": "Zephaniah",
    "Hageo": "Haggai",
    "Zacarías": "Zechariah",
    "Malaquías": "Malachi",
    # New Testament
    "Mateo": "Matthew",
    "Marcos": "Mark",
    "Lucas": "Luke",
    "Juan": "John",
    "Hechos": "Acts",
    "Romanos": "Romans",
    "1 Corintios": "1 Corinthians",
    "2 Corintios": "2 Corinthians",
    "Gálatas": "Galatians",
    "Efesios": "Ephesians",
    "Filipenses": "Philippians",
    "Colosenses": "Colossians",
    "1 Tesalonicenses": "1 Thessalonians",
    "2 Tesalonicenses": "2 Thessalonians",
    "1 Timoteo": "1 Timothy",
    "2 Timoteo": "2 Timothy",
    "Tito": "Titus",
    "Filemón": "Philemon",
    "Hebreos": "Hebrews",
    "Santiago": "James",
    "1 Pedro": "1 Peter",
    "2 Pedro": "2 Peter",
    "1 Juan": "1 John",
    "2 Juan": "2 John",
    "3 Juan": "3 John",
    "Judas": "Jude",
    "Apocalipsis": "Revelation",
}

# French book names (Louis Segond 1910) → Standard English names
FRENCH_BOOK_NAMES = {
    # Old Testament
    "Genèse": "Genesis",
    "Exode": "Exodus",
    "Lévitique": "Leviticus",
    "Nombres": "Numbers",
    "Deutéronome": "Deuteronomy",
    "Josué": "Joshua",
    "Juges": "Judges",
    "Ruth": "Ruth",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Rois": "1 Kings",
    "2 Rois": "2 Kings",
    "1 Chroniques": "1 Chronicles",
    "2 Chroniques": "2 Chronicles",
    "Esdras": "Ezra",
    "Néhémie": "Nehemiah",
    "Esther": "Esther",
    "Job": "Job",
    "Psaumes": "Psalms",
    "Proverbes": "Proverbs",
    "Ecclésiaste": "Ecclesiastes",
    "Cantique des Cantiques": "Song of Solomon",
    "Ésaïe": "Isaiah",
    "Jérémie": "Jeremiah",
    "Lamentations": "Lamentations",
    "Ézéchiel": "Ezekiel",
    "Daniel": "Daniel",
    "Osée": "Hosea",
    "Joël": "Joel",
    "Amos": "Amos",
    "Abdias": "Obadiah",
    "Jonas": "Jonah",
    "Michée": "Micah",
    "Nahum": "Nahum",
    "Habacuc": "Habakkuk",
    "Sophonie": "Zephaniah",
    "Aggée": "Haggai",
    "Zacharie": "Zechariah",
    "Malachie": "Malachi",
    # New Testament
    "Matthieu": "Matthew",
    "Marc": "Mark",
    "Luc": "Luke",
    "Jean": "John",
    "Actes des Apôtres": "Acts",
    "Romains": "Romans",
    "1 Corinthiens": "1 Corinthians",
    "2 Corinthiens": "2 Corinthians",
    "Galates": "Galatians",
    "Éphésiens": "Ephesians",
    "Philippiens": "Philippians",
    "Colossiens": "Colossians",
    "1 Thessaloniciens": "1 Thessalonians",
    "2 Thessaloniciens": "2 Thessalonians",
    "1 Timothée": "1 Timothy",
    "2 Timothée": "2 Timothy",
    "Tite": "Titus",
    "Philémon": "Philemon",
    "Hébreux": "Hebrews",
    "Jacques": "James",
    "1 Pierre": "1 Peter",
    "2 Pierre": "2 Peter",
    "1 Jean": "1 John",
    "2 Jean": "2 John",
    "3 Jean": "3 John",
    "Jude": "Jude",
    "Apocalypse": "Revelation",
}

# Portuguese book names (Almeida Atualizada) → Standard English names
PORTUGUESE_BOOK_NAMES = {
    # Old Testament
    "Gênesis": "Genesis",
    "Êxodo": "Exodus",
    "Levítico": "Leviticus",
    "Números": "Numbers",
    "Deuteronômio": "Deuteronomy",
    "Josué": "Joshua",
    "Juízes": "Judges",
    "Rute": "Ruth",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Reis": "1 Kings",
    "2 Reis": "2 Kings",
    "1 Crônicas": "1 Chronicles",
    "2 Crônicas": "2 Chronicles",
    "Esdras": "Ezra",
    "Neemias": "Nehemiah",
    "Ester": "Esther",
    "Jó": "Job",
    "Salmos": "Psalms",
    "Provérbios": "Proverbs",
    "Eclesiastes": "Ecclesiastes",
    "Cântico dos Cânticos": "Song of Solomon",
    "Isaías": "Isaiah",
    "Jeremias": "Jeremiah",
    "Lamentações": "Lamentations",
    "Ezequiel": "Ezekiel",
    "Daniel": "Daniel",
    "Oseias": "Hosea",
    "Joel": "Joel",
    "Amós": "Amos",
    "Obadias": "Obadiah",
    "Jonas": "Jonah",
    "Miquéias": "Micah",
    "Naum": "Nahum",
    "Habacuque": "Habakkuk",
    "Sofonias": "Zephaniah",
    "Ageu": "Haggai",
    "Zacarias": "Zechariah",
    "Malaquias": "Malachi",
    # New Testament
    "Mateus": "Matthew",
    "Marcos": "Mark",
    "Lucas": "Luke",
    "João": "John",
    "Atos": "Acts",
    "Romanos": "Romans",
    "1 Coríntios": "1 Corinthians",
    "2 Coríntios": "2 Corinthians",
    "Gálatas": "Galatians",
    "Efésios": "Ephesians",
    "Filipenses": "Philippians",
    "Colossenses": "Colossians",
    "1 Tessalonicenses": "1 Thessalonians",
    "2 Tessalonicenses": "2 Thessalonians",
    "1 Timóteo": "1 Timothy",
    "2 Timóteo": "2 Timothy",
    "Tito": "Titus",
    "Filemom": "Philemon",
    "Hebreus": "Hebrews",
    "Tiago": "James",
    "1 Pedro": "1 Peter",
    "2 Pedro": "2 Peter",
    "1 João": "1 John",
    "2 João": "2 John",
    "3 João": "3 John",
    "Judas": "Jude",
    "Apocalipse": "Revelation",
}

# Arabic book names (Smith & Van Dyke) → Standard English names
ARABIC_BOOK_NAMES = {
    # Old Testament
    "تكوين": "Genesis",
    "خروج": "Exodus",
    "لاويين": "Leviticus",
    "عدد": "Numbers",
    "تثنية": "Deuteronomy",
    "يشوع": "Joshua",
    "القضاة": "Judges",
    "راعوث": "Ruth",
    "1 صموئيل": "1 Samuel",
    "2 صموئيل": "2 Samuel",
    "1 الملوك": "1 Kings",
    "2 الملوك": "2 Kings",
    "1 أخبار الأيام": "1 Chronicles",
    "2 أخبار الأيام": "2 Chronicles",
    "عزرا": "Ezra",
    "نحميا": "Nehemiah",
    "أستير": "Esther",
    "أيوب": "Job",
    "المزامير": "Psalms",
    "الأمثال": "Proverbs",
    "الجامعة": "Ecclesiastes",
    "نشيد الأنشاد": "Song of Solomon",
    "إشعياء": "Isaiah",
    "إرميا": "Jeremiah",
    "مراثي إرميا": "Lamentations",
    "حزقيال": "Ezekiel",
    "دانيال": "Daniel",
    "هوشع": "Hosea",
    "يوئيل": "Joel",
    "عاموس": "Amos",
    "عوبديا": "Obadiah",
    "يونان": "Jonah",
    "ميخا": "Micah",
    "ناحوم": "Nahum",
    "حبقوق": "Habakkuk",
    "صفنيا": "Zephaniah",
    "حجي": "Haggai",
    "زكريا": "Zechariah",
    "ملاخي": "Malachi",
    # New Testament
    "متى": "Matthew",
    "مرقس": "Mark",
    "لوقا": "Luke",
    "يوحنا": "John",
    "أعمال الرسل": "Acts",
    "رومية": "Romans",
    "1 كورنثوس": "1 Corinthians",
    "2 كورنثوس": "2 Corinthians",
    "غلاطية": "Galatians",
    "أفسس": "Ephesians",
    "فيليبي": "Philippians",
    "كولوسي": "Colossians",
    "1 تسالونيكي": "1 Thessalonians",
    "2 تسالونيكي": "2 Thessalonians",
    "1 تيموثاوس": "1 Timothy",
    "2 تيموثاوس": "2 Timothy",
    "تيطس": "Titus",
    "فليمون": "Philemon",
    "عبرانيين": "Hebrews",
    "يعقوب": "James",
    "1 بطرس": "1 Peter",
    "2 بطرس": "2 Peter",
    "1 يوحنا": "1 John",
    "2 يوحنا": "2 John",
    "3 يوحنا": "3 John",
    "يهوذا": "Jude",
    "الرؤيا": "Revelation",
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
