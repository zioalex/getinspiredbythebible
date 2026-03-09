"""
Translation configurations and book name mappings for multilingual Bible support.

This module contains:
- Translation metadata (language, source URLs, etc.)
- Book name mappings (Italian/German/Spanish/French/Portuguese/Arabic/Russian/Chinese/Hindi/Korean → English)
- Data source configurations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADDING A NEW LANGUAGE — CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When adding a new language/translation, you must update ALL of the following
or the app will silently fall back to English for that language:

 1. scripts/translations.py (THIS FILE)
    a. Add a <LANGUAGE>_BOOK_NAMES dict  (localized name → English name, 66 books)
    b. Add an entry to TRANSLATIONS dict with keys:
         code, name, language, language_code, description, source, url,
         book_names, license, is_default
    c. source must be one of: "getbible", "thiagobodruk", "scrollmapper", "manual"
    d. url=None is allowed ONLY when source="manual" (no free download source exists)

 2. scripts/init.sql
    Add an INSERT row for the translation so the DB is seeded on fresh deploy.
    Or regenerate via:
      python -c "from translations import generate_translations_sql; print(generate_translations_sql())"

 3. api/utils/language.py
    a. Add ISO code to SUPPORTED_LANGUAGES list
    b. Add entry to LANGUAGE_TRANSLATIONS dict  (e.g. "ru": ["synodal"])
    c. Add entry to TRANSLATION_INFO dict
    d. Add ENGLISH_TO_<LANGUAGE>_BOOKS dict (English → localized, for display)
    e. Add to get_localized_book_name() book_map dict

 4. frontend/messages/<locale>.json
    Create the UI translation file for the new locale.

 5. frontend/src/i18n/routing.ts
    Add the locale code to the locales array.

 6. frontend/src/components/LanguageSwitcher.tsx
    Add the locale label.

 7. frontend/src/app/[locale]/layout.tsx
    Add an hreflang alternate entry.

 8. api/chat/prompts.py
    Add to LANGUAGE_NAMES and SOURCE_ATTRIBUTION_EXAMPLES.

 9. Run all tests:
      cd api && pytest -m "not network" -q
    And check specifically:
      pytest tests/test_translations.py tests/test_multilingual_integration.py -q -m "not network"

10. Count check — update the assertion in:
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

# Russian book names (Synodal Translation) → Standard English names
# Notes:
#   - The getbible "synodal" feed uses genitive/dative forms for book titles
#     (e.g. "Иисуса Навина", "Судей", "1-я Царств") rather than the
#     nominative headings used in many print Bibles.  Both forms are mapped
#     so the loader is robust to either representation.
#   - The feed includes deuterocanonical / apocryphal books not present in the
#     canonical 66-book Protestant Bible (Tobit, Judith, Maccabees, etc.).
#     Those names intentionally have no mapping and will be logged as
#     "Unknown book" and skipped, which is the desired behaviour.
#   - NT epistles use short dative forms in the feed: "Иакову", "1-е Петру",
#     "Римлянам", "1-е Коринфянам", "Иуде", "Деяния", etc.
RUSSIAN_BOOK_NAMES = {
    # ── Old Testament ────────────────────────────────────────────────────────
    "Бытие": "Genesis",
    "Исход": "Exodus",
    "Левит": "Leviticus",
    "Числа": "Numbers",
    "Второзаконие": "Deuteronomy",
    # Joshua — genitive form used in getbible feed
    "Иисуса Навина": "Joshua",
    "Иисус Навин": "Joshua",  # nominative alias
    # Judges — genitive form used in getbible feed
    "Судей": "Judges",
    "Судьи": "Judges",  # nominative alias
    "Руфь": "Ruth",
    # Samuel / Kings — getbible uses "-я" ordinal suffix
    "1-я Царств": "1 Samuel",
    "1 Царств": "1 Samuel",  # alternate form
    "2-я Царств": "2 Samuel",
    "2 Царств": "2 Samuel",
    "3-я Царств": "1 Kings",
    "3 Царств": "1 Kings",
    "4-я Царств": "2 Kings",
    "4 Царств": "2 Kings",
    # Chronicles — "-я" ordinal form
    "1-я Паралипоменон": "1 Chronicles",
    "1 Паралипоменон": "1 Chronicles",
    "2-я Паралипоменон": "2 Chronicles",
    "2 Паралипоменон": "2 Chronicles",
    # Ezra — genitive in feed
    "Ездры": "Ezra",
    "Ездра": "Ezra",  # nominative alias
    # Nehemiah — genitive in feed
    "Неемии": "Nehemiah",
    "Неемия": "Nehemiah",  # nominative alias
    "Есфирь": "Esther",
    "Иов": "Job",
    "Псалтирь": "Psalms",
    "Притчи": "Proverbs",
    "Екклесиаст": "Ecclesiastes",
    # Song of Songs — getbible uses "Песнь Песней"
    "Песнь Песней": "Song of Solomon",
    "Песня Песней": "Song of Solomon",  # alternate nominative form
    "Исаия": "Isaiah",
    "Иеремия": "Jeremiah",
    "Плач Иеремии": "Lamentations",
    # Ezekiel — getbible uses "Иезекииль" (two и)
    "Иезекииль": "Ezekiel",
    "Иезекиль": "Ezekiel",  # one-и variant (kept for robustness)
    "Даниил": "Daniel",
    "Осия": "Hosea",
    "Иоиль": "Joel",
    "Амос": "Amos",
    "Авдий": "Obadiah",
    "Иона": "Jonah",
    "Михей": "Micah",
    "Наум": "Nahum",
    "Аввакум": "Habakkuk",
    "Софония": "Zephaniah",
    "Аггей": "Haggai",
    "Захария": "Zechariah",
    "Малахия": "Malachi",
    # ── New Testament ─────────────────────────────────────────────────────────
    "Матфей": "Matthew",
    "Марк": "Mark",
    "Лука": "Luke",
    "Иоанн": "John",
    # Acts — getbible uses short form "Деяния"
    "Деяния": "Acts",
    "Деяния апостолов": "Acts",  # full form alias
    "Римлянам": "Romans",
    # Corinthians — getbible uses "-е" ordinal suffix
    "1-е Коринфянам": "1 Corinthians",
    "1 Коринфянам": "1 Corinthians",
    "2-е Коринфянам": "2 Corinthians",
    "2 Коринфянам": "2 Corinthians",
    "Галатам": "Galatians",
    "Ефесянам": "Ephesians",
    "Филиппийцам": "Philippians",
    "Колоссянам": "Colossians",
    # Thessalonians — "-е" ordinal suffix
    "1-е Фессалоникийцам": "1 Thessalonians",
    "1 Фессалоникийцам": "1 Thessalonians",
    "2-е Фессалоникийцам": "2 Thessalonians",
    "2 Фессалоникийцам": "2 Thessalonians",
    # Timothy — "-е" ordinal suffix
    "1-е Тимофею": "1 Timothy",
    "1 Тимофею": "1 Timothy",
    "2-е Тимофею": "2 Timothy",
    "2 Тимофею": "2 Timothy",
    "Титу": "Titus",
    "Филимону": "Philemon",
    "Евреям": "Hebrews",
    # James — getbible uses dative "Иакову"
    "Иакову": "James",
    "Иаков": "James",  # nominative alias
    # Peter — dative form in getbible feed
    "1-е Петру": "1 Peter",
    "1 Петра": "1 Peter",  # genitive alias
    "2-е Петру": "2 Peter",
    "2 Петра": "2 Peter",
    # John epistles — dative form in getbible feed
    "1-е Иоанну": "1 John",
    "1 Иоанна": "1 John",
    "2-е Иоанну": "2 John",
    "2 Иоанна": "2 John",
    "3-е Иоанну": "3 John",
    "3 Иоанна": "3 John",
    # Jude — dative "Иуде" in getbible feed
    "Иуде": "Jude",
    "Иуда": "Jude",  # nominative alias
    "Откровение": "Revelation",
}

# Chinese book names (Union Version Simplified) → Standard English names
# Notes:
#   - Genesis may arrive with a UTF-8 BOM (\ufeff) prefix from the getbible API feed;
#     both forms are mapped to handle this gracefully.
#   - Revelation: the getbible CUS feed uses Traditional characters (啟示錄);
#     the Simplified form (启示录) is kept as an alias for robustness.
CHINESE_BOOK_NAMES = {
    "创世记": "Genesis",
    "\ufeff创世记": "Genesis",  # BOM variant from getbible API feed
    "出埃及记": "Exodus",
    "利未记": "Leviticus",
    "民数记": "Numbers",
    "申命记": "Deuteronomy",
    "约书亚记": "Joshua",
    "士师记": "Judges",
    "路得记": "Ruth",
    "撒母耳记上": "1 Samuel",
    "撒母耳记下": "2 Samuel",
    "列王纪上": "1 Kings",
    "列王纪下": "2 Kings",
    "历代志上": "1 Chronicles",
    "历代志下": "2 Chronicles",
    "以斯拉记": "Ezra",
    "尼希米记": "Nehemiah",
    "以斯帖记": "Esther",
    "约伯记": "Job",
    "诗篇": "Psalms",
    "箴言": "Proverbs",
    "传道书": "Ecclesiastes",
    "雅歌": "Song of Solomon",
    "以赛亚书": "Isaiah",
    "耶利米书": "Jeremiah",
    "耶利米哀歌": "Lamentations",
    "以西结书": "Ezekiel",
    "但以理书": "Daniel",
    "何西阿书": "Hosea",
    "约珥书": "Joel",
    "阿摩司书": "Amos",
    "俄巴底亚书": "Obadiah",
    "约拿书": "Jonah",
    "弥迦书": "Micah",
    "那鸿书": "Nahum",
    "哈巴谷书": "Habakkuk",
    "西番雅书": "Zephaniah",
    "哈该书": "Haggai",
    "撒迦利亚书": "Zechariah",
    "玛拉基书": "Malachi",
    "马太福音": "Matthew",
    "马可福音": "Mark",
    "路加福音": "Luke",
    "约翰福音": "John",
    "使徒行传": "Acts",
    "罗马书": "Romans",
    "哥林多前书": "1 Corinthians",
    "哥林多后书": "2 Corinthians",
    "加拉太书": "Galatians",
    "以弗所书": "Ephesians",
    "腓立比书": "Philippians",
    "歌罗西书": "Colossians",
    "帖撒罗尼迦前书": "1 Thessalonians",
    "帖撒罗尼迦后书": "2 Thessalonians",
    "提摩太前书": "1 Timothy",
    "提摩太后书": "2 Timothy",
    "提多书": "Titus",
    "腓利门书": "Philemon",
    "希伯来书": "Hebrews",
    "雅各书": "James",
    "彼得前书": "1 Peter",
    "彼得后书": "2 Peter",
    "约翰一书": "1 John",
    "约翰二书": "2 John",
    "约翰三书": "3 John",
    "犹大书": "Jude",
    "啟示錄": "Revelation",  # Traditional characters — actual name in getbible CUS feed
    "启示录": "Revelation",  # Simplified alias for robustness
}

# Hindi book names (IRV Bible) → Standard English names
HINDI_BOOK_NAMES = {
    "उत्पत्ति": "Genesis",
    "निर्गमन": "Exodus",
    "लैव्यव्यवस्था": "Leviticus",
    "गिनती": "Numbers",
    "व्यवस्थाविवरण": "Deuteronomy",
    "यहोशू": "Joshua",
    "न्यायियों": "Judges",
    "रूत": "Ruth",
    "1 शमूएल": "1 Samuel",
    "2 शमूएल": "2 Samuel",
    "1 राजाओं": "1 Kings",
    "2 राजाओं": "2 Kings",
    "1 इतिहास": "1 Chronicles",
    "2 इतिहास": "2 Chronicles",
    "एज्रा": "Ezra",
    "नहेम्याह": "Nehemiah",
    "एस्तेर": "Esther",
    "अय्यूब": "Job",
    "भजन संहिता": "Psalms",
    "नीतिवचन": "Proverbs",
    "सभोपदेशक": "Ecclesiastes",
    "श्रेष्ठगीत": "Song of Solomon",
    "यशायाह": "Isaiah",
    "यिर्मयाह": "Jeremiah",
    "विलापगीत": "Lamentations",
    "यहेजकेल": "Ezekiel",
    "दानिय्येल": "Daniel",
    "होशे": "Hosea",
    "योएल": "Joel",
    "आमोस": "Amos",
    "ओबद्याह": "Obadiah",
    "योना": "Jonah",
    "मीका": "Micah",
    "नहूम": "Nahum",
    "हबक्कूक": "Habakkuk",
    "सपन्याह": "Zephaniah",
    "हाग्गै": "Haggai",
    "जकर्याह": "Zechariah",
    "मलाकी": "Malachi",
    "मत्ती": "Matthew",
    "मरकुस": "Mark",
    "लूका": "Luke",
    "यूहन्ना": "John",
    "प्रेरितों के काम": "Acts",
    "रोमियों": "Romans",
    "1 कुरिन्थियों": "1 Corinthians",
    "2 कुरिन्थियों": "2 Corinthians",
    "गलातियों": "Galatians",
    "इफिसियों": "Ephesians",
    "फिलिप्पियों": "Philippians",
    "कुलुस्सियों": "Colossians",
    "1 थिस्सलुनीकियों": "1 Thessalonians",
    "2 थिस्सलुनीकियों": "2 Thessalonians",
    "1 तीमुथियुस": "1 Timothy",
    "2 तीमुथियुस": "2 Timothy",
    "तीतुस": "Titus",
    "फिलेमोन": "Philemon",
    "इब्रानियों": "Hebrews",
    "याकूब": "James",
    "1 पतरस": "1 Peter",
    "2 पतरस": "2 Peter",
    "1 यूहन्ना": "1 John",
    "2 यूहन्ना": "2 John",
    "3 यूहन्ना": "3 John",
    "यहूदा": "Jude",
    "प्रकाशितवाक्य": "Revelation",
}

# Korean book names (Korean Revised Version) → Standard English names
KOREAN_BOOK_NAMES = {
    "창세기": "Genesis",
    "출애굽기": "Exodus",
    "레위기": "Leviticus",
    "민수기": "Numbers",
    "신명기": "Deuteronomy",
    "여호수아": "Joshua",
    "사사기": "Judges",
    "룻기": "Ruth",
    "사무엘상": "1 Samuel",
    "사무엘하": "2 Samuel",
    "열왕기상": "1 Kings",
    "열왕기하": "2 Kings",
    "역대상": "1 Chronicles",
    "역대하": "2 Chronicles",
    "에스라": "Ezra",
    "느헤미야": "Nehemiah",
    "에스더": "Esther",
    "욥기": "Job",
    "시편": "Psalms",
    "잠언": "Proverbs",
    "전도서": "Ecclesiastes",
    "아가": "Song of Solomon",
    "이사야": "Isaiah",
    "예레미야": "Jeremiah",
    "예레미야 애가": "Lamentations",  # actual getbible API name (with space)
    "예레미야애가": "Lamentations",  # alternate form without space (kept for robustness)
    "에스겔": "Ezekiel",
    "다니엘": "Daniel",
    "호세아": "Hosea",
    "요엘": "Joel",
    "아모스": "Amos",
    "오바댜": "Obadiah",
    "요나": "Jonah",
    "미가": "Micah",
    "나훔": "Nahum",
    "하박국": "Habakkuk",
    "스바냐": "Zephaniah",
    "학개": "Haggai",
    "스가랴": "Zechariah",
    "말라기": "Malachi",
    "마태복음": "Matthew",
    "마가복음": "Mark",
    "누가복음": "Luke",
    "요한복음": "John",
    "사도행전": "Acts",
    "로마서": "Romans",
    "고린도전서": "1 Corinthians",
    "고린도후서": "2 Corinthians",
    "갈라디아서": "Galatians",
    "에베소서": "Ephesians",
    "빌립보서": "Philippians",
    "골로새서": "Colossians",
    "데살로니가전서": "1 Thessalonians",
    "데살로니가후서": "2 Thessalonians",
    "디모데전서": "1 Timothy",
    "디모데후서": "2 Timothy",
    "디도서": "Titus",
    "빌레몬서": "Philemon",
    "히브리서": "Hebrews",
    "야고보서": "James",
    "베드로전서": "1 Peter",
    "베드로후서": "2 Peter",
    "요한일서": "1 John",
    "요한이서": "2 John",
    "요한삼서": "3 John",
    "유다서": "Jude",
    "요한계시록": "Revelation",
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
