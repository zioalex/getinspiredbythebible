"""
Single source of truth for Bible book name mappings across all supported translations.

Every ``ENGLISH_TO_*`` dict maps the 66-book Protestant canon from standard English
names to the localized names used by that translation's source feed (getbible.net etc.).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADDING A NEW TRANSLATION — WHAT TO DO HERE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Add an ``ENGLISH_TO_<LANGUAGE>`` dict (66 entries, English → localized).
   Use the *primary* (canonical) localized form as the value — i.e. the form
   that actually appears as the book name in the translation's source feed.

2. If the language uses grammatical case inflection or definite-article prefixes
   on book names (e.g. Russian, Arabic, Ukrainian), add a ``<LANGUAGE>_CITATION_FORMS``
   dict immediately after the ``ENGLISH_TO_*`` dict.  Citation forms are the
   inflected versions an LLM naturally produces when citing a verse
   (e.g. Russian genitive "Иоанна 3:16" vs nominative canonical "Иоанн").
   See RUSSIAN_CITATION_FORMS below for the pattern to follow.

3. If the feed uses *alias* forms (alternate grammar, BOM prefix, no-space
   variant, etc.) that differ from the canonical value, add a ``<LANGUAGE>_ALIASES``
   dict immediately after the ``ENGLISH_TO_*`` dict (and after any
   ``*_CITATION_FORMS`` dict) so that ``normalize_book_name`` can still
   reverse-map them to English.

4. Register the translation in ``TRANSLATION_REGISTRY``:
       "my_code": ENGLISH_TO_MY_LANGUAGE

5. Add your new ``*_CITATION_FORMS`` and/or ``*_ALIASES`` dicts to the
   ``EXTRA_REVERSE_MAPPINGS`` merge at the bottom of this file.

That's it. The following update automatically:
  • ``api/utils/book_names.py``   — reverse dicts, LOCALIZED_TO_ENGLISH
  • ``api/utils/verse_parser.py`` — ALL_BOOK_NAMES regex set
  • ``scripts/translations.py``   — <LANGUAGE>_BOOK_NAMES (via reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ---------------------------------------------------------------------------
# Forward mappings  (English → localized)
# ---------------------------------------------------------------------------

# Italian (Riveduta 1927 / ita1927)
ENGLISH_TO_ITALIAN: dict[str, str] = {
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

# German (Schlachter 1951 / schlachter)
ENGLISH_TO_GERMAN: dict[str, str] = {
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

# German aliases (common alternate spellings found in German Bibles / LLM output)
GERMAN_ALIASES: dict[str, str] = {
    "Rut": "Ruth",  # alternate for "Ruth"
    "Ester": "Esther",  # alternate for "Esther"
    "Hohes Lied": "Song of Solomon",  # alternate for "Hohelied"
    "Zefanja": "Zephaniah",  # alternate for "Zephanja" (Luther vs Schlachter orthography)
}

# Spanish (Reina Valera 1909 / valera)
ENGLISH_TO_SPANISH: dict[str, str] = {
    "Genesis": "Génesis",
    "Exodus": "Éxodo",
    "Leviticus": "Levítico",
    "Numbers": "Números",
    "Deuteronomy": "Deuteronomio",
    "Joshua": "Josué",
    "Judges": "Jueces",
    "Ruth": "Rut",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Kings": "1 Reyes",
    "2 Kings": "2 Reyes",
    "1 Chronicles": "1 Crónicas",
    "2 Chronicles": "2 Crónicas",
    "Ezra": "Esdras",
    "Nehemiah": "Nehemías",
    "Esther": "Ester",
    "Job": "Job",
    "Psalms": "Salmos",
    "Proverbs": "Proverbios",
    "Ecclesiastes": "Eclesiastés",
    "Song of Solomon": "Cantares",
    "Isaiah": "Isaías",
    "Jeremiah": "Jeremías",
    "Lamentations": "Lamentaciones",
    "Ezekiel": "Ezequiel",
    "Daniel": "Daniel",
    "Hosea": "Oseas",
    "Joel": "Joel",
    "Amos": "Amós",
    "Obadiah": "Abdías",
    "Jonah": "Jonás",
    "Micah": "Miqueas",
    "Nahum": "Nahúm",
    "Habakkuk": "Habacuc",
    "Zephaniah": "Sofonías",
    "Haggai": "Hageo",
    "Zechariah": "Zacarías",
    "Malachi": "Malaquías",
    "Matthew": "Mateo",
    "Mark": "Marcos",
    "Luke": "Lucas",
    "John": "Juan",
    "Acts": "Hechos",
    "Romans": "Romanos",
    "1 Corinthians": "1 Corintios",
    "2 Corinthians": "2 Corintios",
    "Galatians": "Gálatas",
    "Ephesians": "Efesios",
    "Philippians": "Filipenses",
    "Colossians": "Colosenses",
    "1 Thessalonians": "1 Tesalonicenses",
    "2 Thessalonians": "2 Tesalonicenses",
    "1 Timothy": "1 Timoteo",
    "2 Timothy": "2 Timoteo",
    "Titus": "Tito",
    "Philemon": "Filemón",
    "Hebrews": "Hebreos",
    "James": "Santiago",
    "1 Peter": "1 Pedro",
    "2 Peter": "2 Pedro",
    "1 John": "1 Juan",
    "2 John": "2 Juan",
    "3 John": "3 Juan",
    "Jude": "Judas",
    "Revelation": "Apocalipsis",
}

# French (Louis Segond 1910 / ls1910)
ENGLISH_TO_FRENCH: dict[str, str] = {
    "Genesis": "Genèse",
    "Exodus": "Exode",
    "Leviticus": "Lévitique",
    "Numbers": "Nombres",
    "Deuteronomy": "Deutéronome",
    "Joshua": "Josué",
    "Judges": "Juges",
    "Ruth": "Ruth",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Kings": "1 Rois",
    "2 Kings": "2 Rois",
    "1 Chronicles": "1 Chroniques",
    "2 Chronicles": "2 Chroniques",
    "Ezra": "Esdras",
    "Nehemiah": "Néhémie",
    "Esther": "Esther",
    "Job": "Job",
    "Psalms": "Psaumes",
    "Proverbs": "Proverbes",
    "Ecclesiastes": "Ecclésiaste",
    "Song of Solomon": "Cantique des Cantiques",
    "Isaiah": "Ésaïe",
    "Jeremiah": "Jérémie",
    "Lamentations": "Lamentations",
    "Ezekiel": "Ézéchiel",
    "Daniel": "Daniel",
    "Hosea": "Osée",
    "Joel": "Joël",
    "Amos": "Amos",
    "Obadiah": "Abdias",
    "Jonah": "Jonas",
    "Micah": "Michée",
    "Nahum": "Nahum",
    "Habakkuk": "Habacuc",
    "Zephaniah": "Sophonie",
    "Haggai": "Aggée",
    "Zechariah": "Zacharie",
    "Malachi": "Malachie",
    "Matthew": "Matthieu",
    "Mark": "Marc",
    "Luke": "Luc",
    "John": "Jean",
    "Acts": "Actes des Apôtres",
    "Romans": "Romains",
    "1 Corinthians": "1 Corinthiens",
    "2 Corinthians": "2 Corinthiens",
    "Galatians": "Galates",
    "Ephesians": "Éphésiens",
    "Philippians": "Philippiens",
    "Colossians": "Colossiens",
    "1 Thessalonians": "1 Thessaloniciens",
    "2 Thessalonians": "2 Thessaloniciens",
    "1 Timothy": "1 Timothée",
    "2 Timothy": "2 Timothée",
    "Titus": "Tite",
    "Philemon": "Philémon",
    "Hebrews": "Hébreux",
    "James": "Jacques",
    "1 Peter": "1 Pierre",
    "2 Peter": "2 Pierre",
    "1 John": "1 Jean",
    "2 John": "2 Jean",
    "3 John": "3 Jean",
    "Jude": "Jude",
    "Revelation": "Apocalypse",
}

# Portuguese (Almeida Atualizada / almeida)
ENGLISH_TO_PORTUGUESE: dict[str, str] = {
    "Genesis": "Gênesis",
    "Exodus": "Êxodo",
    "Leviticus": "Levítico",
    "Numbers": "Números",
    "Deuteronomy": "Deuteronômio",
    "Joshua": "Josué",
    "Judges": "Juízes",
    "Ruth": "Rute",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Kings": "1 Reis",
    "2 Kings": "2 Reis",
    "1 Chronicles": "1 Crônicas",
    "2 Chronicles": "2 Crônicas",
    "Ezra": "Esdras",
    "Nehemiah": "Neemias",
    "Esther": "Ester",
    "Job": "Jó",
    "Psalms": "Salmos",
    "Proverbs": "Provérbios",
    "Ecclesiastes": "Eclesiastes",
    "Song of Solomon": "Cântico dos Cânticos",
    "Isaiah": "Isaías",
    "Jeremiah": "Jeremias",
    "Lamentations": "Lamentações",
    "Ezekiel": "Ezequiel",
    "Daniel": "Daniel",
    "Hosea": "Oseias",
    "Joel": "Joel",
    "Amos": "Amós",
    "Obadiah": "Obadias",
    "Jonah": "Jonas",
    "Micah": "Miquéias",
    "Nahum": "Naum",
    "Habakkuk": "Habacuque",
    "Zephaniah": "Sofonias",
    "Haggai": "Ageu",
    "Zechariah": "Zacarias",
    "Malachi": "Malaquias",
    "Matthew": "Mateus",
    "Mark": "Marcos",
    "Luke": "Lucas",
    "John": "João",
    "Acts": "Atos",
    "Romans": "Romanos",
    "1 Corinthians": "1 Coríntios",
    "2 Corinthians": "2 Coríntios",
    "Galatians": "Gálatas",
    "Ephesians": "Efésios",
    "Philippians": "Filipenses",
    "Colossians": "Colossenses",
    "1 Thessalonians": "1 Tessalonicenses",
    "2 Thessalonians": "2 Tessalonicenses",
    "1 Timothy": "1 Timóteo",
    "2 Timothy": "2 Timóteo",
    "Titus": "Tito",
    "Philemon": "Filemom",
    "Hebrews": "Hebreus",
    "James": "Tiago",
    "1 Peter": "1 Pedro",
    "2 Peter": "2 Pedro",
    "1 John": "1 João",
    "2 John": "2 João",
    "3 John": "3 João",
    "Jude": "Judas",
    "Revelation": "Apocalipse",
}

# Arabic (Smith & Van Dyke / arabicsv)
# Note: Arabic uses definite-article prefixes (ال) on some book names in the feed.
# LLMs commonly produce forms without the article, singular forms, or simplified
# spellings.  ARABIC_CITATION_FORMS (below the main dict) maps these variants
# back to the canonical English name.
ENGLISH_TO_ARABIC: dict[str, str] = {
    "Genesis": "تكوين",
    "Exodus": "خروج",
    "Leviticus": "لاويين",
    "Numbers": "عدد",
    "Deuteronomy": "تثنية",
    "Joshua": "يشوع",
    "Judges": "القضاة",
    "Ruth": "راعوث",
    "1 Samuel": "1 صموئيل",
    "2 Samuel": "2 صموئيل",
    "1 Kings": "1 الملوك",
    "2 Kings": "2 الملوك",
    "1 Chronicles": "1 أخبار الأيام",
    "2 Chronicles": "2 أخبار الأيام",
    "Ezra": "عزرا",
    "Nehemiah": "نحميا",
    "Esther": "أستير",
    "Job": "أيوب",
    "Psalms": "المزامير",
    "Proverbs": "الأمثال",
    "Ecclesiastes": "الجامعة",
    "Song of Solomon": "نشيد الأنشاد",
    "Isaiah": "إشعياء",
    "Jeremiah": "إرميا",
    "Lamentations": "مراثي إرميا",
    "Ezekiel": "حزقيال",
    "Daniel": "دانيال",
    "Hosea": "هوشع",
    "Joel": "يوئيل",
    "Amos": "عاموس",
    "Obadiah": "عوبديا",
    "Jonah": "يونان",
    "Micah": "ميخا",
    "Nahum": "ناحوم",
    "Habakkuk": "حبقوق",
    "Zephaniah": "صفنيا",
    "Haggai": "حجي",
    "Zechariah": "زكريا",
    "Malachi": "ملاخي",
    "Matthew": "متى",
    "Mark": "مرقس",
    "Luke": "لوقا",
    "John": "يوحنا",
    "Acts": "أعمال الرسل",
    "Romans": "رومية",
    "1 Corinthians": "1 كورنثوس",
    "2 Corinthians": "2 كورنثوس",
    "Galatians": "غلاطية",
    "Ephesians": "أفسس",
    "Philippians": "فيليبي",
    "Colossians": "كولوسي",
    "1 Thessalonians": "1 تسالونيكي",
    "2 Thessalonians": "2 تسالونيكي",
    "1 Timothy": "1 تيموثاوس",
    "2 Timothy": "2 تيموثاوس",
    "Titus": "تيطس",
    "Philemon": "فليمون",
    "Hebrews": "عبرانيين",
    "James": "يعقوب",
    "1 Peter": "1 بطرس",
    "2 Peter": "2 بطرس",
    "1 John": "1 يوحنا",
    "2 John": "2 يوحنا",
    "3 John": "3 يوحنا",
    "Jude": "يهوذا",
    "Revelation": "الرؤيا",
}

# Arabic citation forms — alternate forms LLMs produce when citing verses.
# The Smith & Van Dyke feed uses definite-article forms (المزامير, الأمثال, etc.)
# but LLMs commonly output bare/singular forms (مزمور, أمثال, etc.).
ARABIC_CITATION_FORMS: dict[str, str] = {
    # Psalms — singular "مزمور" (psalm) vs feed's "المزامير" (the psalms)
    "مزمور": "Psalms",
    # Psalms — plural without article
    "مزامير": "Psalms",
    # Proverbs — without definite article
    "أمثال": "Proverbs",
    # Ecclesiastes — without definite article
    "جامعة": "Ecclesiastes",
    # Judges — without definite article
    "قضاة": "Judges",
    # Revelation — without definite article
    "رؤيا": "Revelation",
    # Song of Solomon — common LLM short form
    "نشيد الأناشيد": "Song of Solomon",
    # Acts — shortened form without "الرسل"
    "أعمال": "Acts",
}

# Russian (Synodal Translation 1876 / synodal)
# Canonical forms match the primary book name used in the getbible Synodal feed.
# Citation forms (genitive case) and alias forms are in the dicts below.
ENGLISH_TO_RUSSIAN: dict[str, str] = {
    "Genesis": "Бытие",
    "Exodus": "Исход",
    "Leviticus": "Левит",
    "Numbers": "Числа",
    "Deuteronomy": "Второзаконие",
    "Joshua": "Иисуса Навина",
    "Judges": "Судей",
    "Ruth": "Руфь",
    "1 Samuel": "1-я Царств",
    "2 Samuel": "2-я Царств",
    "1 Kings": "3-я Царств",
    "2 Kings": "4-я Царств",
    "1 Chronicles": "1-я Паралипоменон",
    "2 Chronicles": "2-я Паралипоменон",
    "Ezra": "Ездры",
    "Nehemiah": "Неемии",
    "Esther": "Есфирь",
    "Job": "Иов",
    "Psalms": "Псалтирь",
    "Proverbs": "Притчи",
    "Ecclesiastes": "Екклесиаст",
    "Song of Solomon": "Песнь Песней",
    "Isaiah": "Исаия",
    "Jeremiah": "Иеремия",
    "Lamentations": "Плач Иеремии",
    "Ezekiel": "Иезекииль",
    "Daniel": "Даниил",
    "Hosea": "Осия",
    "Joel": "Иоиль",
    "Amos": "Амос",
    "Obadiah": "Авдий",
    "Jonah": "Иона",
    "Micah": "Михей",
    "Nahum": "Наум",
    "Habakkuk": "Аввакум",
    "Zephaniah": "Софония",
    "Haggai": "Аггей",
    "Zechariah": "Захария",
    "Malachi": "Малахия",
    "Matthew": "Матфей",
    "Mark": "Марк",
    "Luke": "Лука",
    "John": "Иоанн",
    "Acts": "Деяния",
    "Romans": "Римлянам",
    "1 Corinthians": "1-е Коринфянам",
    "2 Corinthians": "2-е Коринфянам",
    "Galatians": "Галатам",
    "Ephesians": "Ефесянам",
    "Philippians": "Филиппийцам",
    "Colossians": "Колоссянам",
    "1 Thessalonians": "1-е Фессалоникийцам",
    "2 Thessalonians": "2-е Фессалоникийцам",
    "1 Timothy": "1-е Тимофею",
    "2 Timothy": "2-е Тимофею",
    "Titus": "Титу",
    "Philemon": "Филимону",
    "Hebrews": "Евреям",
    "James": "Иакову",
    "1 Peter": "1-е Петру",
    "2 Peter": "2-е Петру",
    "1 John": "1-е Иоанну",
    "2 John": "2-е Иоанну",
    "3 John": "3-е Иоанну",
    "Jude": "Иуде",
    "Revelation": "Откровение",
}

# Russian genitive citation forms — the inflected forms an LLM naturally produces
# when citing a verse in Russian (genitive case: "Иоанна 3:16", not nominative "Иоанн").
# Russian grammar requires the genitive case for book names used in citations, so
# LLM output will almost always use these forms rather than the Synodal canonical names.
# Only unambiguous single-book genitives are included here; numbered-book genitives
# (e.g. "1 Петра", "1 Иоанна") live in RUSSIAN_ALIASES since they carry the number.
RUSSIAN_CITATION_FORMS: dict[str, str] = {
    "Иоанна": "John",
    "Матфея": "Matthew",
    "Луки": "Luke",
    "Марка": "Mark",
    "Деяний": "Acts",
    "Откровения": "Revelation",
    "Бытия": "Genesis",
    "Псалтири": "Psalms",
    "Притч": "Proverbs",
    "Екклесиаста": "Ecclesiastes",
    "Исаии": "Isaiah",
    "Иеремии": "Jeremiah",
    "Исхода": "Exodus",
    "Левита": "Leviticus",
    "Числ": "Numbers",
    "Второзакония": "Deuteronomy",
    "Руфи": "Ruth",
    "Иакова": "James",
}

# Russian alternate names / aliases (book names that differ from the canonical
# Synodal feed forms — alternate ordinal styles, alternate naming traditions,
# spelling variants, and numbered-book genitive forms).
RUSSIAN_ALIASES: dict[str, str] = {
    # Joshua — traditional nominative name (feed uses genitive "Иисуса Навина")
    "Иисус Навин": "Joshua",
    # Judges — nominative form (feed uses genitive "Судей")
    "Судьи": "Judges",
    # Ezra — nominative form (feed uses genitive "Ездры")
    "Ездра": "Ezra",
    # Nehemiah — nominative form (feed uses genitive "Неемии")
    "Неемия": "Nehemiah",
    # Samuel / Kings — alternate ordinal forms without dash (feed uses "1-я Царств" etc.)
    "1 Царств": "1 Samuel",
    "2 Царств": "2 Samuel",
    "3 Царств": "1 Kings",
    "4 Царств": "2 Kings",
    "1 Паралипоменон": "1 Chronicles",
    "2 Паралипоменон": "2 Chronicles",
    # Song of Solomon — alternate name
    "Песня Песней": "Song of Solomon",
    # Ezekiel — one-и spelling variant
    "Иезекиль": "Ezekiel",
    # Acts — full form with "apostles"
    "Деяния апостолов": "Acts",
    # Corinthians — no-dash ordinal forms
    "1 Коринфянам": "1 Corinthians",
    "2 Коринфянам": "2 Corinthians",
    # Thessalonians — no-dash ordinal forms
    "1 Фессалоникийцам": "1 Thessalonians",
    "2 Фессалоникийцам": "2 Thessalonians",
    # Timothy — no-dash ordinal forms
    "1 Тимофею": "1 Timothy",
    "2 Тимофею": "2 Timothy",
    # James — nominative alias (feed uses dative "Иакову")
    "Иаков": "James",
    # Peter — numbered genitive forms (unambiguous because number is present)
    "1 Петра": "1 Peter",
    "2 Петра": "2 Peter",
    # John epistles — numbered genitive forms
    "1 Иоанна": "1 John",
    "2 Иоанна": "2 John",
    "3 Иоанна": "3 John",
    # Jude — nominative alias (feed uses dative "Иуде")
    "Иуда": "Jude",
    # ── Russian abbreviations (commonly used by LLMs) ────────────────────────
    "Ин": "John",
    "Мф": "Matthew",
    "Мк": "Mark",
    "Лк": "Luke",
    "Пс": "Psalms",
    "Рим": "Romans",
    "Быт": "Genesis",
    "Ис": "Isaiah",
    "Откр": "Revelation",
    "Деян": "Acts",
    "Гал": "Galatians",
    "Еф": "Ephesians",
    "Кол": "Colossians",
    "Евр": "Hebrews",
    "Иак": "James",
    "Флп": "Philippians",
    "Флм": "Philemon",
    # ── ё/е variants ─────────────────────────────────────────────────────────
    "Иёв": "Job",  # ё variant of Иов
}

# Chinese Union Version Simplified (CUS / cuv)
# Revelation uses Traditional characters in the actual getbible CUS feed.
# Simplified alias and BOM variant are in CHINESE_ALIASES below.
ENGLISH_TO_CHINESE: dict[str, str] = {
    "Genesis": "创世记",
    "Exodus": "出埃及记",
    "Leviticus": "利未记",
    "Numbers": "民数记",
    "Deuteronomy": "申命记",
    "Joshua": "约书亚记",
    "Judges": "士师记",
    "Ruth": "路得记",
    "1 Samuel": "撒母耳记上",
    "2 Samuel": "撒母耳记下",
    "1 Kings": "列王纪上",
    "2 Kings": "列王纪下",
    "1 Chronicles": "历代志上",
    "2 Chronicles": "历代志下",
    "Ezra": "以斯拉记",
    "Nehemiah": "尼希米记",
    "Esther": "以斯帖记",
    "Job": "约伯记",
    "Psalms": "诗篇",
    "Proverbs": "箴言",
    "Ecclesiastes": "传道书",
    "Song of Solomon": "雅歌",
    "Isaiah": "以赛亚书",
    "Jeremiah": "耶利米书",
    "Lamentations": "耶利米哀歌",
    "Ezekiel": "以西结书",
    "Daniel": "但以理书",
    "Hosea": "何西阿书",
    "Joel": "约珥书",
    "Amos": "阿摩司书",
    "Obadiah": "俄巴底亚书",
    "Jonah": "约拿书",
    "Micah": "弥迦书",
    "Nahum": "那鸿书",
    "Habakkuk": "哈巴谷书",
    "Zephaniah": "西番雅书",
    "Haggai": "哈该书",
    "Zechariah": "撒迦利亚书",
    "Malachi": "玛拉基书",
    "Matthew": "马太福音",
    "Mark": "马可福音",
    "Luke": "路加福音",
    "John": "约翰福音",
    "Acts": "使徒行传",
    "Romans": "罗马书",
    "1 Corinthians": "哥林多前书",
    "2 Corinthians": "哥林多后书",
    "Galatians": "加拉太书",
    "Ephesians": "以弗所书",
    "Philippians": "腓立比书",
    "Colossians": "歌罗西书",
    "1 Thessalonians": "帖撒罗尼迦前书",
    "2 Thessalonians": "帖撒罗尼迦后书",
    "1 Timothy": "提摩太前书",
    "2 Timothy": "提摩太后书",
    "Titus": "提多书",
    "Philemon": "腓利门书",
    "Hebrews": "希伯来书",
    "James": "雅各书",
    "1 Peter": "彼得前书",
    "2 Peter": "彼得后书",
    "1 John": "约翰一书",
    "2 John": "约翰二书",
    "3 John": "约翰三书",
    "Jude": "犹大书",
    "Revelation": "啟示錄",  # Traditional characters — actual name in getbible CUS feed
}

# Chinese aliases (encoding variants, simplified/traditional script variants,
# 记↔纪 character swaps, and Catholic 思高本 book names).
CHINESE_ALIASES: dict[str, str] = {
    # ── encoding / script variants ────────────────────────────────────────────
    "\ufeff创世记": "Genesis",  # Genesis with UTF-8 BOM (getbible API feed artifact)
    "启示录": "Revelation",  # Revelation in Simplified characters (feed uses Traditional "啟示錄")
    # ── 记↔纪 swaps (jì — both mean "record"; LLMs frequently confuse them) ──
    "创世纪": "Genesis",
    "出埃及纪": "Exodus",
    "利未纪": "Leviticus",
    "民数纪": "Numbers",
    "申命纪": "Deuteronomy",
    "约书亚纪": "Joshua",
    "士师纪": "Judges",
    "路得纪": "Ruth",
    "撒母耳纪上": "1 Samuel",
    "撒母耳纪下": "2 Samuel",
    "列王记上": "1 Kings",  # CUV uses 纪 for Kings; variant uses 记
    "列王记下": "2 Kings",
    "以斯拉纪": "Ezra",
    "尼希米纪": "Nehemiah",
    "以斯帖纪": "Esther",
    "约伯纪": "Job",
    # ── Catholic 思高本 (Studium Biblicum) names ──────────────────────────────
    "玛窦福音": "Matthew",
    "马尔谷福音": "Mark",
    "若望福音": "John",
    "宗徒大事录": "Acts",
    "默示录": "Revelation",
    "格林多前书": "1 Corinthians",
    "格林多后书": "2 Corinthians",
    "若望一书": "1 John",
    "若望二书": "2 John",
    "若望三书": "3 John",
    "雅各伯书": "James",
    "犹达书": "Jude",
}

# Korean Revised Version (개역개정 / krv)
# Lamentations with-space is the canonical API form; no-space alias is in KOREAN_ALIASES.
ENGLISH_TO_KOREAN: dict[str, str] = {
    "Genesis": "창세기",
    "Exodus": "출애굽기",
    "Leviticus": "레위기",
    "Numbers": "민수기",
    "Deuteronomy": "신명기",
    "Joshua": "여호수아",
    "Judges": "사사기",
    "Ruth": "룻기",
    "1 Samuel": "사무엘상",
    "2 Samuel": "사무엘하",
    "1 Kings": "열왕기상",
    "2 Kings": "열왕기하",
    "1 Chronicles": "역대상",
    "2 Chronicles": "역대하",
    "Ezra": "에스라",
    "Nehemiah": "느헤미야",
    "Esther": "에스더",
    "Job": "욥기",
    "Psalms": "시편",
    "Proverbs": "잠언",
    "Ecclesiastes": "전도서",
    "Song of Solomon": "아가",
    "Isaiah": "이사야",
    "Jeremiah": "예레미야",
    "Lamentations": "예레미야 애가",  # actual getbible API name (with space)
    "Ezekiel": "에스겔",
    "Daniel": "다니엘",
    "Hosea": "호세아",
    "Joel": "요엘",
    "Amos": "아모스",
    "Obadiah": "오바댜",
    "Jonah": "요나",
    "Micah": "미가",
    "Nahum": "나훔",
    "Habakkuk": "하박국",
    "Zephaniah": "스바냐",
    "Haggai": "학개",
    "Zechariah": "스가랴",
    "Malachi": "말라기",
    "Matthew": "마태복음",
    "Mark": "마가복음",
    "Luke": "누가복음",
    "John": "요한복음",
    "Acts": "사도행전",
    "Romans": "로마서",
    "1 Corinthians": "고린도전서",
    "2 Corinthians": "고린도후서",
    "Galatians": "갈라디아서",
    "Ephesians": "에베소서",
    "Philippians": "빌립보서",
    "Colossians": "골로새서",
    "1 Thessalonians": "데살로니가전서",
    "2 Thessalonians": "데살로니가후서",
    "1 Timothy": "디모데전서",
    "2 Timothy": "디모데후서",
    "Titus": "디도서",
    "Philemon": "빌레몬서",
    "Hebrews": "히브리서",
    "James": "야고보서",
    "1 Peter": "베드로전서",
    "2 Peter": "베드로후서",
    "1 John": "요한일서",
    "2 John": "요한이서",
    "3 John": "요한삼서",
    "Jude": "유다서",
    "Revelation": "요한계시록",
}

# Korean aliases (spacing/orthographic variants)
KOREAN_ALIASES: dict[str, str] = {
    "예레미야애가": "Lamentations",  # Lamentations without space (LLM and some sources omit it)
    "계시록": "Revelation",  # Short form of 요한계시록 (without 요한)
    "애가": "Lamentations",  # Short form of 예레미야 애가 (without 예레미야)
    "행전": "Acts",  # Short form of 사도행전 (without 사도)
}

# Alternate Hindi spellings/transliterations that LLMs commonly produce but are
# not the canonical IRV Bible keys in ENGLISH_TO_HINDI.
HINDI_ALIASES: dict[str, str] = {
    "लेवियतियुस": "Leviticus",  # Transliterated form; IRV uses लैव्यव्यवस्था
}

# Hindi (IRV Bible / hindi)
ENGLISH_TO_HINDI: dict[str, str] = {
    "Genesis": "उत्पत्ति",
    "Exodus": "निर्गमन",
    "Leviticus": "लैव्यव्यवस्था",
    "Numbers": "गिनती",
    "Deuteronomy": "व्यवस्थाविवरण",
    "Joshua": "यहोशू",
    "Judges": "न्यायियों",
    "Ruth": "रूत",
    "1 Samuel": "1 शमूएल",
    "2 Samuel": "2 शमूएल",
    "1 Kings": "1 राजाओं",
    "2 Kings": "2 राजाओं",
    "1 Chronicles": "1 इतिहास",
    "2 Chronicles": "2 इतिहास",
    "Ezra": "एज्रा",
    "Nehemiah": "नहेम्याह",
    "Esther": "एस्तेर",
    "Job": "अय्यूब",
    "Psalms": "भजन संहिता",
    "Proverbs": "नीतिवचन",
    "Ecclesiastes": "सभोपदेशक",
    "Song of Solomon": "श्रेष्ठगीत",
    "Isaiah": "यशायाह",
    "Jeremiah": "यिर्मयाह",
    "Lamentations": "विलापगीत",
    "Ezekiel": "यहेजकेल",
    "Daniel": "दानिय्येल",
    "Hosea": "होशे",
    "Joel": "योएल",
    "Amos": "आमोस",
    "Obadiah": "ओबद्याह",
    "Jonah": "योना",
    "Micah": "मीका",
    "Nahum": "नहूम",
    "Habakkuk": "हबक्कूक",
    "Zephaniah": "सपन्याह",
    "Haggai": "हाग्गै",
    "Zechariah": "जकर्याह",
    "Malachi": "मलाकी",
    "Matthew": "मत्ती",
    "Mark": "मरकुस",
    "Luke": "लूका",
    "John": "यूहन्ना",
    "Acts": "प्रेरितों के काम",
    "Romans": "रोमियों",
    "1 Corinthians": "1 कुरिन्थियों",
    "2 Corinthians": "2 कुरिन्थियों",
    "Galatians": "गलातियों",
    "Ephesians": "इफिसियों",
    "Philippians": "फिलिप्पियों",
    "Colossians": "कुलुस्सियों",
    "1 Thessalonians": "1 थिस्सलुनीकियों",
    "2 Thessalonians": "2 थिस्सलुनीकियों",
    "1 Timothy": "1 तीमुथियुस",
    "2 Timothy": "2 तीमुथियुस",
    "Titus": "तीतुस",
    "Philemon": "फिलेमोन",
    "Hebrews": "इब्रानियों",
    "James": "याकूब",
    "1 Peter": "1 पतरस",
    "2 Peter": "2 पतरस",
    "1 John": "1 यूहन्ना",
    "2 John": "2 यूहन्ना",
    "3 John": "3 यूहन्ना",
    "Jude": "यहूदा",
    "Revelation": "प्रकाशितवाक्य",
}

# ---------------------------------------------------------------------------
# Registry  (translation code → English→localized dict, or None for English)
# ---------------------------------------------------------------------------

TRANSLATION_REGISTRY: dict[str, dict[str, str] | None] = {
    "ita1927": ENGLISH_TO_ITALIAN,
    "schlachter": ENGLISH_TO_GERMAN,
    "luther1912": ENGLISH_TO_GERMAN,
    "elberfelder1905": ENGLISH_TO_GERMAN,
    "valera": ENGLISH_TO_SPANISH,
    "ls1910": ENGLISH_TO_FRENCH,
    "almeida": ENGLISH_TO_PORTUGUESE,
    "arabicsv": ENGLISH_TO_ARABIC,
    "synodal": ENGLISH_TO_RUSSIAN,
    "cuv": ENGLISH_TO_CHINESE,
    "hindi": ENGLISH_TO_HINDI,
    "krv": ENGLISH_TO_KOREAN,
    # English translations need no mapping
    "kjv": None,
    "web": None,
}

# ---------------------------------------------------------------------------
# Citation forms and aliases — merged into a single reverse-lookup dict.
#
# WHAT ARE CITATION FORMS?
# ────────────────────────
# In inflecting languages (Russian, Ukrainian, Arabic, etc.) book names change
# their ending depending on grammatical case.  When an LLM cites a verse it
# naturally uses the *genitive* case (e.g. Russian "Иоанна 3:16"), not the
# nominative form stored in the ENGLISH_TO_* dict ("Иоанн").  Without these
# mappings, verse-reference parsing silently fails for those languages.
#
# WHICH LANGUAGES CURRENTLY HAVE CITATION FORMS?
# ───────────────────────────────────────────────
# • Russian — RUSSIAN_CITATION_FORMS (18 unambiguous genitive forms)
#   Ambiguous forms ("Петра" = 1 Peter or 2 Peter) are intentionally excluded.
#
# ADDING A NEW INFLECTING LANGUAGE?
# ──────────────────────────────────
# 1. Collect the genitive (citation) forms an LLM produces for that language.
# 2. Create a  <LANGUAGE>_CITATION_FORMS  dict immediately after the
#    ENGLISH_TO_<LANGUAGE> dict in this file.
# 3. Add  **<LANGUAGE>_CITATION_FORMS  to the merge below.
# 4. Exclude forms that are ambiguous across books (e.g. a suffix shared by
#    multiple books without a disambiguating number prefix).
# ---------------------------------------------------------------------------

ITALIAN_ALIASES: dict[str, str] = {
    # Singular form used by LLMs when referring to an individual Psalm (e.g. "Salmo 60").
    # Also covers Spanish and Portuguese where the same singular "Salmo" is used
    # (canonical forms are "Salmos" in both those languages).
    "Salmo": "Psalms",
}

FRENCH_ALIASES: dict[str, str] = {
    # Singular form used by LLMs when referring to an individual Psalm (e.g. "Psaume 23").
    # The canonical French form registered in ENGLISH_TO_FRENCH is "Psaumes" (plural).
    "Psaume": "Psalms",
}

# English singular / abbreviated forms that LLMs commonly produce but are not
# canonical keys in ENGLISH_TO_ITALIAN (which uses "Psalms" with the trailing 's').
ENGLISH_ALIASES: dict[str, str] = {
    "Psalm": "Psalms",  # singular form, e.g. "Psalm 23" — very common in English prose
    "Song of Solomon": "Song of Solomon",  # identity mapping so the alias set includes it
    # ── Song of Solomon alternate titles ─────────────────────────────────
    "Song of Songs": "Song of Solomon",
    "Songs": "Song of Solomon",
    "Canticles": "Song of Solomon",
    "Cant": "Song of Solomon",
    "SoS": "Song of Solomon",
    # ── Common misspelling ────────────────────────────────────────────────
    "Revelations": "Revelation",
    # ── Numbered-book short forms (2–3 letter abbreviations) ─────────────
    # Old Testament
    "1 Sam": "1 Samuel",
    "2 Sam": "2 Samuel",
    "1 Kgs": "1 Kings",
    "2 Kgs": "2 Kings",
    "1 Chr": "1 Chronicles",
    "2 Chr": "2 Chronicles",
    # New Testament
    "1 Cor": "1 Corinthians",
    "2 Cor": "2 Corinthians",
    "1 Thess": "1 Thessalonians",
    "2 Thess": "2 Thessalonians",
    "1 Tim": "1 Timothy",
    "2 Tim": "2 Timothy",
    "1 Pet": "1 Peter",
    "2 Pet": "2 Peter",
    "1 Jn": "1 John",
    "2 Jn": "2 John",
    "3 Jn": "3 John",
}

EXTRA_REVERSE_MAPPINGS: dict[str, str] = {
    **RUSSIAN_CITATION_FORMS,
    **RUSSIAN_ALIASES,
    **ARABIC_CITATION_FORMS,
    **CHINESE_ALIASES,
    **KOREAN_ALIASES,
    **HINDI_ALIASES,
    **GERMAN_ALIASES,
    **ITALIAN_ALIASES,
    **FRENCH_ALIASES,
    **ENGLISH_ALIASES,
    # add new language citation forms and aliases here
}
