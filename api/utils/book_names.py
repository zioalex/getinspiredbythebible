"""
Book name localization utilities.

Maps English book names to localized versions for different translations.
"""

# Italian book names (Riveduta 1927) - reverse mapping from English
ENGLISH_TO_ITALIAN = {
    "Genesis": "Genesi",
    "Exodus": "Esodo",
    "Leviticus": "Levitico",
    "Numbers": "Numeri",
    "Deuteronomy": "Deuteronomio",
    "Joshua": "Giosuè",
    "Judges": "Giudici",
    "Ruth": "Rut",
    "1 Samuel": "1 Samuele",
    "2 Samuel": "2 Samuele",
    "1 Kings": "1 Re",
    "2 Kings": "2 Re",
    "1 Chronicles": "1 Cronache",
    "2 Chronicles": "2 Cronache",
    "Ezra": "Esdra",
    "Nehemiah": "Nehemia",
    "Esther": "Ester",
    "Job": "Giobbe",
    "Psalms": "Salmi",
    "Proverbs": "Proverbi",
    "Ecclesiastes": "Ecclesiaste",
    "Song of Solomon": "Cantico dei Cantici",
    "Isaiah": "Isaia",
    "Jeremiah": "Geremia",
    "Lamentations": "Lamentazioni",
    "Ezekiel": "Ezechiele",
    "Daniel": "Daniele",
    "Hosea": "Osea",
    "Joel": "Gioele",
    "Amos": "Amos",
    "Obadiah": "Abdia",
    "Jonah": "Giona",
    "Micah": "Michea",
    "Nahum": "Nahum",
    "Habakkuk": "Abacuc",
    "Zephaniah": "Sofonia",
    "Haggai": "Aggeo",
    "Zechariah": "Zaccaria",
    "Malachi": "Malachia",
    "Matthew": "Matteo",
    "Mark": "Marco",
    "Luke": "Luca",
    "John": "Giovanni",
    "Acts": "Atti",
    "Romans": "Romani",
    "1 Corinthians": "1 Corinzi",
    "2 Corinthians": "2 Corinzi",
    "Galatians": "Galati",
    "Ephesians": "Efesini",
    "Philippians": "Filippesi",
    "Colossians": "Colossesi",
    "1 Thessalonians": "1 Tessalonicesi",
    "2 Thessalonians": "2 Tessalonicesi",
    "1 Timothy": "1 Timoteo",
    "2 Timothy": "2 Timoteo",
    "Titus": "Tito",
    "Philemon": "Filemone",
    "Hebrews": "Ebrei",
    "James": "Giacomo",
    "1 Peter": "1 Pietro",
    "2 Peter": "2 Pietro",
    "1 John": "1 Giovanni",
    "2 John": "2 Giovanni",
    "3 John": "3 Giovanni",
    "Jude": "Giuda",
    "Revelation": "Apocalisse",
}

# German book names (Schlachter) - reverse mapping from English
ENGLISH_TO_GERMAN = {
    "Genesis": "1. Mose",
    "Exodus": "2. Mose",
    "Leviticus": "3. Mose",
    "Numbers": "4. Mose",
    "Deuteronomy": "5. Mose",
    "Joshua": "Josua",
    "Judges": "Richter",
    "Ruth": "Ruth",
    "1 Samuel": "1. Samuel",
    "2 Samuel": "2. Samuel",
    "1 Kings": "1. Könige",
    "2 Kings": "2. Könige",
    "1 Chronicles": "1. Chronik",
    "2 Chronicles": "2. Chronik",
    "Ezra": "Esra",
    "Nehemiah": "Nehemia",
    "Esther": "Esther",
    "Job": "Hiob",
    "Psalms": "Psalmen",
    "Proverbs": "Sprüche",
    "Ecclesiastes": "Prediger",
    "Song of Solomon": "Hohelied",
    "Isaiah": "Jesaja",
    "Jeremiah": "Jeremia",
    "Lamentations": "Klagelieder",
    "Ezekiel": "Hesekiel",
    "Daniel": "Daniel",
    "Hosea": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obadiah": "Obadja",
    "Jonah": "Jona",
    "Micah": "Micha",
    "Nahum": "Nahum",
    "Habakkuk": "Habakuk",
    "Zephaniah": "Zephanja",
    "Haggai": "Haggai",
    "Zechariah": "Sacharja",
    "Malachi": "Maleachi",
    "Matthew": "Matthäus",
    "Mark": "Markus",
    "Luke": "Lukas",
    "John": "Johannes",
    "Acts": "Apostelgeschichte",
    "Romans": "Römer",
    "1 Corinthians": "1. Korinther",
    "2 Corinthians": "2. Korinther",
    "Galatians": "Galater",
    "Ephesians": "Epheser",
    "Philippians": "Philipper",
    "Colossians": "Kolosser",
    "1 Thessalonians": "1. Thessalonicher",
    "2 Thessalonians": "2. Thessalonicher",
    "1 Timothy": "1. Timotheus",
    "2 Timothy": "2. Timotheus",
    "Titus": "Titus",
    "Philemon": "Philemon",
    "Hebrews": "Hebräer",
    "James": "Jakobus",
    "1 Peter": "1. Petrus",
    "2 Peter": "2. Petrus",
    "1 John": "1. Johannes",
    "2 John": "2. Johannes",
    "3 John": "3. Johannes",
    "Jude": "Judas",
    "Revelation": "Offenbarung",
}

# Mapping of translation codes to their book name mappings
TRANSLATION_BOOK_NAMES = {
    "ita1927": ENGLISH_TO_ITALIAN,
    "schlachter": ENGLISH_TO_GERMAN,
    # English translations don't need mapping
    "kjv": None,
    "web": None,
}


def get_localized_book_name(english_name: str, translation_code: str) -> str:
    """
    Get the localized book name for a given English book name.

    Args:
        english_name: Standard English book name (e.g., "Genesis", "Psalms")
        translation_code: Translation code (e.g., "ita1927", "schlachter")

    Returns:
        Localized book name (e.g., "Genesi", "Psalmen") or English name if no mapping
    """
    book_names = TRANSLATION_BOOK_NAMES.get(translation_code)

    if book_names is None:
        # English translations use standard names
        return english_name

    return book_names.get(english_name, english_name)
