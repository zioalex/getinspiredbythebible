"""
Tests for translation configurations and book name mappings
"""

import sys
import time
from pathlib import Path

import httpx
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from translations import (
    ARABIC_BOOK_NAMES,
    CHINESE_BOOK_NAMES,
    FRENCH_BOOK_NAMES,
    GERMAN_BOOK_NAMES,
    ITALIAN_BOOK_NAMES,
    KOREAN_BOOK_NAMES,
    PORTUGUESE_BOOK_NAMES,
    RUSSIAN_BOOK_NAMES,
    SPANISH_BOOK_NAMES,
    TRANSLATIONS,
    get_translation_config,
    list_available_translations,
    map_book_name,
)

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries


def _fetch_with_retry(url: str, method: str = "head", timeout: float = 30.0) -> httpx.Response:
    """Fetch a URL with retries to handle transient network failures in CI.

    Retries on connection errors *and* on transient upstream 5xx responses
    (getBible sits behind Cloudflare and intermittently returns 502/503/520),
    so these live-URL checks don't flake when the origin has a momentary blip.
    """
    last_error = None
    last_response = None
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                if method == "head":
                    response = client.head(url)
                    if response.status_code == 405:
                        response = client.get(url)
                else:
                    response = client.get(url)
            last_response = response
            # Retry transient upstream 5xx (e.g. Cloudflare 502/503/520).
            if response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            return response
        except httpx.RequestError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    if last_response is not None:
        return last_response
    raise last_error  # type: ignore[misc]


def test_italian_book_names_complete():
    """Test that all 66 Bible books have Italian mappings"""
    assert len(ITALIAN_BOOK_NAMES) == 66
    # Check a few key books
    assert ITALIAN_BOOK_NAMES["Genesi"] == "Genesis"
    assert ITALIAN_BOOK_NAMES["Matteo"] == "Matthew"
    assert ITALIAN_BOOK_NAMES["Apocalisse"] == "Revelation"


def test_german_book_names_complete():
    """Test that all 66 Bible books have German mappings (plus alternate spellings)"""
    # 66 books + 4 alternate spellings (Rut, Ester, Hohes Lied, Zefanja)
    assert len(GERMAN_BOOK_NAMES) == 70
    # Verify all 66 unique English book names are covered
    unique_english_names = set(GERMAN_BOOK_NAMES.values())
    assert len(unique_english_names) == 66
    # Check a few key books
    assert GERMAN_BOOK_NAMES["1. Mose"] == "Genesis"
    assert GERMAN_BOOK_NAMES["Matthäus"] == "Matthew"
    assert GERMAN_BOOK_NAMES["Offenbarung"] == "Revelation"
    # Check alternate spellings
    assert GERMAN_BOOK_NAMES["Rut"] == "Ruth"
    assert GERMAN_BOOK_NAMES["Ester"] == "Esther"
    assert GERMAN_BOOK_NAMES["Hohes Lied"] == "Song of Solomon"
    assert GERMAN_BOOK_NAMES["Zefanja"] == "Zephaniah"


def test_italian_old_testament_books():
    """Test Italian Old Testament book mappings"""
    old_testament_samples = {
        "Genesi": "Genesis",
        "Esodo": "Exodus",
        "Salmi": "Psalms",
        "Isaia": "Isaiah",
        "Geremia": "Jeremiah",
    }
    for italian, english in old_testament_samples.items():
        assert ITALIAN_BOOK_NAMES[italian] == english


def test_italian_new_testament_books():
    """Test Italian New Testament book mappings"""
    new_testament_samples = {
        "Matteo": "Matthew",
        "Marco": "Mark",
        "Luca": "Luke",
        "Giovanni": "John",
        "Romani": "Romans",
        "1 Corinzi": "1 Corinthians",
        "Apocalisse": "Revelation",
    }
    for italian, english in new_testament_samples.items():
        assert ITALIAN_BOOK_NAMES[italian] == english


def test_german_old_testament_books():
    """Test German Old Testament book mappings"""
    old_testament_samples = {
        "1. Mose": "Genesis",
        "2. Mose": "Exodus",
        "Psalmen": "Psalms",
        "Jesaja": "Isaiah",
        "Jeremia": "Jeremiah",
    }
    for german, english in old_testament_samples.items():
        assert GERMAN_BOOK_NAMES[german] == english


def test_german_new_testament_books():
    """Test German New Testament book mappings"""
    new_testament_samples = {
        "Matthäus": "Matthew",
        "Markus": "Mark",
        "Lukas": "Luke",
        "Johannes": "John",
        "Römer": "Romans",
        "1. Korinther": "1 Corinthians",
        "Offenbarung": "Revelation",
    }
    for german, english in new_testament_samples.items():
        assert GERMAN_BOOK_NAMES[german] == english


def test_spanish_book_names_complete():
    """Test that all 66 Bible books have Spanish mappings"""
    assert len(SPANISH_BOOK_NAMES) == 66
    assert SPANISH_BOOK_NAMES["Génesis"] == "Genesis"
    assert SPANISH_BOOK_NAMES["Mateo"] == "Matthew"
    assert SPANISH_BOOK_NAMES["Apocalipsis"] == "Revelation"


def test_french_book_names_complete():
    """Test that all 66 Bible books have French mappings"""
    assert len(FRENCH_BOOK_NAMES) == 66
    assert FRENCH_BOOK_NAMES["Genèse"] == "Genesis"
    assert FRENCH_BOOK_NAMES["Matthieu"] == "Matthew"
    assert FRENCH_BOOK_NAMES["Apocalypse"] == "Revelation"


def test_portuguese_book_names_complete():
    """Test that all 66 Bible books have Portuguese mappings"""
    assert len(PORTUGUESE_BOOK_NAMES) == 66
    assert PORTUGUESE_BOOK_NAMES["Gênesis"] == "Genesis"
    assert PORTUGUESE_BOOK_NAMES["Mateus"] == "Matthew"
    assert PORTUGUESE_BOOK_NAMES["Apocalipse"] == "Revelation"


def test_arabic_book_names_complete():
    """Test that all 66 Bible books have Arabic mappings"""
    assert len(ARABIC_BOOK_NAMES) == 66
    assert ARABIC_BOOK_NAMES["تكوين"] == "Genesis"
    assert ARABIC_BOOK_NAMES["متى"] == "Matthew"
    assert ARABIC_BOOK_NAMES["الرؤيا"] == "Revelation"


def test_all_spanish_books_unique():
    """Test that all Spanish book names map to unique English names"""
    english_names = list(SPANISH_BOOK_NAMES.values())
    assert len(english_names) == len(set(english_names))


def test_all_french_books_unique():
    """Test that all French book names map to unique English names"""
    english_names = list(FRENCH_BOOK_NAMES.values())
    assert len(english_names) == len(set(english_names))


def test_all_portuguese_books_unique():
    """Test that all Portuguese book names map to unique English names"""
    english_names = list(PORTUGUESE_BOOK_NAMES.values())
    assert len(english_names) == len(set(english_names))


def test_all_arabic_books_unique():
    """Test that all Arabic book names map to unique English names"""
    english_names = list(ARABIC_BOOK_NAMES.values())
    assert len(english_names) == len(set(english_names))


def test_chinese_book_names_complete():
    """Test that all 66 Bible books have Chinese mappings (plus BOM and alias variants)"""
    # 66 canonical + 1 BOM variant + 1 Simplified Revelation alias
    # + 16 记↔纪 character-swap aliases + 12 Catholic 思高本 name aliases = 96
    assert len(CHINESE_BOOK_NAMES) == 96
    # Verify exactly 66 unique English book names are covered
    unique_english_names = set(CHINESE_BOOK_NAMES.values())
    assert len(unique_english_names) == 66
    # Check key books
    assert CHINESE_BOOK_NAMES["创世记"] == "Genesis"
    assert CHINESE_BOOK_NAMES["\ufeff创世记"] == "Genesis"  # BOM variant from getbible API
    assert CHINESE_BOOK_NAMES["马太福音"] == "Matthew"
    assert CHINESE_BOOK_NAMES["啟示錄"] == "Revelation"  # Traditional — actual API name
    assert CHINESE_BOOK_NAMES["启示录"] == "Revelation"  # Simplified alias


def test_chinese_all_books_unique_english():
    """Test that all Chinese book names map to the 66 unique English book names"""
    unique_english_names = set(CHINESE_BOOK_NAMES.values())
    assert len(unique_english_names) == 66


def test_chinese_api_book_names():
    """Test that the exact names returned by the getbible CUS API all resolve correctly.

    These are the names actually returned by https://api.getbible.net/v2/cus.json
    as of March 2026.  The first entry has a BOM; Revelation uses Traditional characters.
    """
    getbible_cus_names = [
        "\ufeff创世记",
        "出埃及记",
        "利未记",
        "民数记",
        "申命记",
        "约书亚记",
        "士师记",
        "路得记",
        "撒母耳记上",
        "撒母耳记下",
        "列王纪上",
        "列王纪下",
        "历代志上",
        "历代志下",
        "以斯拉记",
        "尼希米记",
        "以斯帖记",
        "约伯记",
        "诗篇",
        "箴言",
        "传道书",
        "雅歌",
        "以赛亚书",
        "耶利米书",
        "耶利米哀歌",
        "以西结书",
        "但以理书",
        "何西阿书",
        "约珥书",
        "阿摩司书",
        "俄巴底亚书",
        "约拿书",
        "弥迦书",
        "那鸿书",
        "哈巴谷书",
        "西番雅书",
        "哈该书",
        "撒迦利亚书",
        "玛拉基书",
        "马太福音",
        "马可福音",
        "路加福音",
        "约翰福音",
        "使徒行传",
        "罗马书",
        "哥林多前书",
        "哥林多后书",
        "加拉太书",
        "以弗所书",
        "腓立比书",
        "歌罗西书",
        "帖撒罗尼迦前书",
        "帖撒罗尼迦后书",
        "提摩太前书",
        "提摩太后书",
        "提多书",
        "腓利门书",
        "希伯来书",
        "雅各书",
        "彼得前书",
        "彼得后书",
        "约翰一书",
        "约翰二书",
        "约翰三书",
        "犹大书",
        "啟示錄",
    ]
    missing = [name for name in getbible_cus_names if name not in CHINESE_BOOK_NAMES]
    assert not missing, f"Missing Chinese book names from getbible CUS API: {missing}"
    assert len(getbible_cus_names) == 66


def test_korean_book_names_complete():
    """Test that all 66 Bible books have Korean mappings (plus aliases)"""
    # 66 canonical books + 1 alternate Lamentations (no space) + 3 short-form aliases
    # (계시록=Revelation, 애가=Lamentations, 행전=Acts) = 70
    assert len(KOREAN_BOOK_NAMES) == 70
    unique_english_names = set(KOREAN_BOOK_NAMES.values())
    assert len(unique_english_names) == 66
    # Check key books
    assert KOREAN_BOOK_NAMES["창세기"] == "Genesis"
    assert KOREAN_BOOK_NAMES["마태복음"] == "Matthew"
    assert KOREAN_BOOK_NAMES["요한계시록"] == "Revelation"
    # Lamentations: API uses form WITH space
    assert KOREAN_BOOK_NAMES["예레미야 애가"] == "Lamentations"
    assert KOREAN_BOOK_NAMES["예레미야애가"] == "Lamentations"  # alternate without space
    # Short-form aliases
    assert KOREAN_BOOK_NAMES["계시록"] == "Revelation"
    assert KOREAN_BOOK_NAMES["애가"] == "Lamentations"
    assert KOREAN_BOOK_NAMES["행전"] == "Acts"


def test_korean_api_book_names():
    """Test that the exact names returned by the getbible korean API all resolve correctly.

    These are the names actually returned by https://api.getbible.net/v2/korean.json
    as of March 2026.  Lamentations is '예레미야 애가' (with space).
    """
    getbible_korean_names = [
        "창세기",
        "출애굽기",
        "레위기",
        "민수기",
        "신명기",
        "여호수아",
        "사사기",
        "룻기",
        "사무엘상",
        "사무엘하",
        "열왕기상",
        "열왕기하",
        "역대상",
        "역대하",
        "에스라",
        "느헤미야",
        "에스더",
        "욥기",
        "시편",
        "잠언",
        "전도서",
        "아가",
        "이사야",
        "예레미야",
        "예레미야 애가",
        "에스겔",
        "다니엘",
        "호세아",
        "요엘",
        "아모스",
        "오바댜",
        "요나",
        "미가",
        "나훔",
        "하박국",
        "스바냐",
        "학개",
        "스가랴",
        "말라기",
        "마태복음",
        "마가복음",
        "누가복음",
        "요한복음",
        "사도행전",
        "로마서",
        "고린도전서",
        "고린도후서",
        "갈라디아서",
        "에베소서",
        "빌립보서",
        "골로새서",
        "데살로니가전서",
        "데살로니가후서",
        "디모데전서",
        "디모데후서",
        "디도서",
        "빌레몬서",
        "히브리서",
        "야고보서",
        "베드로전서",
        "베드로후서",
        "요한일서",
        "요한이서",
        "요한삼서",
        "유다서",
        "요한계시록",
    ]
    missing = [name for name in getbible_korean_names if name not in KOREAN_BOOK_NAMES]
    assert not missing, f"Missing Korean book names from getbible korean API: {missing}"
    assert len(getbible_korean_names) == 66


def test_russian_book_names_complete():
    """Test that RUSSIAN_BOOK_NAMES covers all 66 canonical Bible books.

    The Synodal getbible feed uses genitive/dative forms AND includes apocryphal
    books that are intentionally unmapped.  We therefore cannot assert a fixed
    count, but we verify that exactly 66 unique English names are covered.
    """
    unique_english_names = set(RUSSIAN_BOOK_NAMES.values())
    assert len(unique_english_names) == 66
    # Spot-check key books
    assert RUSSIAN_BOOK_NAMES["Бытие"] == "Genesis"
    assert RUSSIAN_BOOK_NAMES["Матфей"] == "Matthew"
    assert RUSSIAN_BOOK_NAMES["Откровение"] == "Revelation"


def test_russian_api_canonical_book_names():
    """Test that the canonical 66-book names from the getbible synodal API resolve.

    The synodal feed returns books in genitive/dative forms plus apocryphal books.
    Only the 66 Protestant-canon books are expected to map; apocrypha are skipped.
    These are the exact canonical names from https://api.getbible.net/v2/synodal.json
    as of March 2026.
    """
    synodal_canonical_names = [
        # OT
        "Бытие",
        "Исход",
        "Левит",
        "Числа",
        "Второзаконие",
        "Иисуса Навина",
        "Судей",
        "Руфь",
        "1-я Царств",
        "2-я Царств",
        "3-я Царств",
        "4-я Царств",
        "1-я Паралипоменон",
        "2-я Паралипоменон",
        "Ездры",
        "Неемии",
        "Есфирь",
        "Иов",
        "Псалтирь",
        "Притчи",
        "Екклесиаст",
        "Песнь Песней",
        "Исаия",
        "Иеремия",
        "Плач Иеремии",
        "Иезекииль",
        "Даниил",
        "Осия",
        "Иоиль",
        "Амос",
        "Авдий",
        "Иона",
        "Михей",
        "Наум",
        "Аввакум",
        "Софония",
        "Аггей",
        "Захария",
        "Малахия",
        # NT
        "Матфей",
        "Марк",
        "Лука",
        "Иоанн",
        "Деяния",
        "Иакову",
        "1-е Петру",
        "2-е Петру",
        "1-е Иоанну",
        "2-е Иоанну",
        "3-е Иоанну",
        "Иуде",
        "Римлянам",
        "1-е Коринфянам",
        "2-е Коринфянам",
        "Галатам",
        "Ефесянам",
        "Филиппийцам",
        "Колоссянам",
        "1-е Фессалоникийцам",
        "2-е Фессалоникийцам",
        "1-е Тимофею",
        "2-е Тимофею",
        "Титу",
        "Филимону",
        "Евреям",
        "Откровение",
    ]
    missing = [name for name in synodal_canonical_names if name not in RUSSIAN_BOOK_NAMES]
    assert not missing, f"Missing Russian book names from getbible synodal API: {missing}"
    assert len(synodal_canonical_names) == 66


def test_translations_config_exists():
    """Test that translations configuration exists for all expected translations"""
    assert "kjv" in TRANSLATIONS
    assert "web" in TRANSLATIONS
    assert "ita1927" in TRANSLATIONS
    assert "schlachter" in TRANSLATIONS
    assert "valera" in TRANSLATIONS
    assert "ls1910" in TRANSLATIONS
    assert "almeida" in TRANSLATIONS
    assert "arabicsv" in TRANSLATIONS


def test_kjv_translation_config():
    """Test KJV translation configuration"""
    kjv = TRANSLATIONS["kjv"]
    assert kjv["code"] == "kjv"
    assert kjv["name"] == "King James Version"
    assert kjv["language"] == "English"
    assert kjv["language_code"] == "en"
    assert kjv["is_default"] is True
    assert kjv["book_names"] is None  # English uses standard names


def test_italian_translation_config():
    """Test Italian translation configuration"""
    ita = TRANSLATIONS["ita1927"]
    assert ita["code"] == "ita1927"
    assert ita["name"] == "Riveduta 1927"
    assert ita["language"] == "Italian"
    assert ita["language_code"] == "it"
    assert ita["is_default"] is False
    assert ita["book_names"] == ITALIAN_BOOK_NAMES


def test_german_translation_config():
    """Test German translation configuration"""
    deu = TRANSLATIONS["schlachter"]
    assert deu["code"] == "schlachter"
    assert deu["name"] == "Schlachter 1951"
    assert deu["language"] == "German"
    assert deu["language_code"] == "de"
    assert deu["is_default"] is False
    assert deu["book_names"] == GERMAN_BOOK_NAMES


def test_get_translation_config():
    """Test get_translation_config function"""
    config = get_translation_config("kjv")
    assert config["code"] == "kjv"
    assert config["name"] == "King James Version"


def test_get_translation_config_invalid():
    """Test get_translation_config with invalid code raises error"""
    try:
        get_translation_config("invalid_code")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown translation code" in str(e)


def test_spanish_translation_config():
    """Test Spanish translation configuration"""
    es = TRANSLATIONS["valera"]
    assert es["code"] == "valera"
    assert es["name"] == "Reina Valera 1909"
    assert es["language"] == "Spanish"
    assert es["language_code"] == "es"
    assert es["is_default"] is False
    assert es["book_names"] == SPANISH_BOOK_NAMES


def test_french_translation_config():
    """Test French translation configuration"""
    fr = TRANSLATIONS["ls1910"]
    assert fr["code"] == "ls1910"
    assert fr["name"] == "Louis Segond 1910"
    assert fr["language"] == "French"
    assert fr["language_code"] == "fr"
    assert fr["is_default"] is False
    assert fr["book_names"] == FRENCH_BOOK_NAMES


def test_portuguese_translation_config():
    """Test Portuguese translation configuration"""
    pt = TRANSLATIONS["almeida"]
    assert pt["code"] == "almeida"
    assert pt["name"] == "Almeida Atualizada"
    assert pt["language"] == "Portuguese"
    assert pt["language_code"] == "pt"
    assert pt["is_default"] is False
    assert pt["book_names"] == PORTUGUESE_BOOK_NAMES


def test_arabic_translation_config():
    """Test Arabic translation configuration"""
    ar = TRANSLATIONS["arabicsv"]
    assert ar["code"] == "arabicsv"
    assert ar["name"] == "Smith & Van Dyke"
    assert ar["language"] == "Arabic"
    assert ar["language_code"] == "ar"
    assert ar["is_default"] is False
    assert ar["book_names"] == ARABIC_BOOK_NAMES


def test_list_available_translations():
    """Test list_available_translations function"""
    translations = list_available_translations()
    # Phase 1 (8): kjv, web, ita1927, schlachter, valera, ls1910, almeida, arabicsv
    # Phase 2 (4): synodal, cuv, hindi, krv
    # German additions (2): luther1912, elberfelder1905
    assert len(translations) == 14

    # Check structure
    assert all("code" in t for t in translations)
    assert all("name" in t for t in translations)
    assert all("language" in t for t in translations)
    assert all("language_code" in t for t in translations)


def test_map_book_name_italian():
    """Test book name mapping for Italian"""
    assert map_book_name("Genesi", "ita1927") == "Genesis"
    assert map_book_name("Matteo", "ita1927") == "Matthew"
    assert map_book_name("Apocalisse", "ita1927") == "Revelation"


def test_map_book_name_german():
    """Test book name mapping for German"""
    assert map_book_name("1. Mose", "schlachter") == "Genesis"
    assert map_book_name("Matthäus", "schlachter") == "Matthew"
    assert map_book_name("Offenbarung", "schlachter") == "Revelation"


def test_map_book_name_spanish():
    """Test book name mapping for Spanish"""
    assert map_book_name("Génesis", "valera") == "Genesis"
    assert map_book_name("Mateo", "valera") == "Matthew"
    assert map_book_name("Apocalipsis", "valera") == "Revelation"


def test_map_book_name_french():
    """Test book name mapping for French"""
    assert map_book_name("Genèse", "ls1910") == "Genesis"
    assert map_book_name("Matthieu", "ls1910") == "Matthew"
    assert map_book_name("Apocalypse", "ls1910") == "Revelation"


def test_map_book_name_portuguese():
    """Test book name mapping for Portuguese"""
    assert map_book_name("Gênesis", "almeida") == "Genesis"
    assert map_book_name("Mateus", "almeida") == "Matthew"
    assert map_book_name("Apocalipse", "almeida") == "Revelation"


def test_map_book_name_arabic():
    """Test book name mapping for Arabic"""
    assert map_book_name("تكوين", "arabicsv") == "Genesis"
    assert map_book_name("متى", "arabicsv") == "Matthew"
    assert map_book_name("الرؤيا", "arabicsv") == "Revelation"


def test_map_book_name_english():
    """Test book name mapping for English (passthrough)"""
    # English translations should return the name as-is
    assert map_book_name("Genesis", "kjv") == "Genesis"
    assert map_book_name("Matthew", "kjv") == "Matthew"
    assert map_book_name("Revelation", "web") == "Revelation"


def test_map_book_name_unknown_book():
    """Test book name mapping with unknown book returns original"""
    # Should return the original name if not in mapping
    assert map_book_name("UnknownBook", "ita1927") == "UnknownBook"


def test_all_italian_books_unique():
    """Test that all Italian book names map to unique English names"""
    english_names = list(ITALIAN_BOOK_NAMES.values())
    assert len(english_names) == len(set(english_names))


def test_all_german_books_unique():
    """Test that all German book names map to the 66 unique English book names"""
    english_names = list(GERMAN_BOOK_NAMES.values())
    unique_english_names = set(english_names)
    # Should have 66 unique English names (some German names are alternates)
    assert len(unique_english_names) == 66


def test_translation_urls_valid():
    """Test that all translation configs have valid URLs.

    Translations with source='manual' have no download URL (url=None) because
    no free public source exists; they require manual data loading.
    """
    for code, config in TRANSLATIONS.items():
        assert "url" in config, f"Translation {code} missing 'url' key"
        if config.get("source") == "manual":
            # Manual-load translations intentionally have no download URL
            assert config["url"] is None, f"Translation {code} (manual) should have url=None"
            continue
        assert config["url"] is not None, f"Translation {code} has None url"
        assert config["url"].startswith("http"), f"Translation {code} url should start with http"
        assert "://" in config["url"], f"Translation {code} url malformed"


def test_translation_sources():
    """Test that translations have valid source specifications.

    'manual' is a valid source for translations that have no free public
    download URL and must be loaded manually (e.g. hindi / IRV).
    """
    valid_sources = ["thiagobodruk", "getbible", "scrollmapper", "manual"]
    for code, config in TRANSLATIONS.items():
        assert "source" in config, f"Translation {code} missing 'source' key"
        assert config["source"] in valid_sources, (
            f"Translation {code} has unknown source: {config['source']}. "
            f"Valid sources: {valid_sources}"
        )


@pytest.mark.network
def test_translation_urls_accessible():
    """
    Test that all Bible translation URLs are accessible.

    This test makes actual HTTP requests with retries to verify the URLs
    are valid. Transient timeouts are retried up to 3 times with backoff.
    Run with: pytest -m network
    Skip with: pytest -m "not network"

    Translations with source='manual' (url=None) are skipped — they have no
    public download URL and are loaded by other means.
    """
    failed_urls = []

    for code, config in TRANSLATIONS.items():
        url = config["url"]
        if url is None:
            # manual-source translations have no download URL — skip
            continue
        try:
            response = _fetch_with_retry(url, method="head")
            if response.status_code != 200:
                failed_urls.append(f"{code}: {url} returned status {response.status_code}")
        except httpx.RequestError as e:
            failed_urls.append(f"{code}: {url} failed after {MAX_RETRIES} retries: {e}")

    if failed_urls:
        pytest.fail(
            "The following Bible translation URLs are not accessible:\n"
            + "\n".join(f"  - {url}" for url in failed_urls)
        )


@pytest.mark.network
def test_translation_urls_return_valid_json():
    """
    Test that all Bible translation URLs return valid JSON with expected structure.

    This test downloads a small portion of each Bible to verify the format.
    Run with: pytest -m network

    Translations with source='manual' (url=None) are skipped — they have no
    public download URL and are loaded by other means.
    """
    for code, config in TRANSLATIONS.items():
        url = config["url"]
        if url is None:
            # manual-source translations have no download URL — skip
            continue
        response = _fetch_with_retry(url, method="get", timeout=60.0)
        assert response.status_code == 200, f"{code}: Failed to fetch {url}"

        data = response.json()

        # Check for expected structure based on source
        if config["source"] == "getbible":
            # getbible.net format has books as keys
            assert isinstance(data, dict), f"{code}: Expected dict from getbible"
            # Should have book data
            assert len(data) > 0, f"{code}: Empty response from {url}"
        elif config["source"] == "thiagobodruk":
            # thiagobodruk format is a list of books
            assert isinstance(data, list), f"{code}: Expected list from thiagobodruk"
            assert len(data) == 66, f"{code}: Expected 66 books, got {len(data)}"
            # Check first book has expected fields
            first_book = data[0]
            assert "name" in first_book, f"{code}: Missing 'name' field"
            assert "chapters" in first_book, f"{code}: Missing 'chapters' field"


def test_init_sql_matches_translations_config():
    """
    Test that scripts/init.sql translation inserts match translations.py config.

    This test ensures the database initialization stays in sync with the
    source of truth (translations.py).
    """
    import re

    # Read init.sql
    init_sql_path = Path(__file__).parent.parent.parent / "scripts" / "init.sql"
    with open(init_sql_path) as f:
        init_sql = f.read()

    # Only parse up to the marker comment to avoid matching other INSERT statements
    marker = "-- END_TRANSLATIONS_INSERT"
    if marker in init_sql:
        init_sql = init_sql[: init_sql.index(marker)]

    # Extract translation codes from init.sql INSERT statement
    # Pattern matches: ('code', 'name', ...
    pattern = r"\('([a-z0-9]+)',\s*'([^']+)',\s*'([^']+)',\s*'([a-z]+)'"
    sql_translations = {}
    for match in re.finditer(pattern, init_sql):
        code, name, language, lang_code = match.groups()
        sql_translations[code] = {
            "name": name,
            "language": language,
            "language_code": lang_code,
        }

    # Verify all translations from config are in init.sql
    for code, config in TRANSLATIONS.items():
        assert code in sql_translations, (
            f"Translation '{code}' from translations.py missing in init.sql. "
            f'Run: python -c "from translations import generate_translations_sql; '
            f'print(generate_translations_sql())"'
        )

        # Verify metadata matches
        sql_trans = sql_translations[code]
        assert sql_trans["name"] == config["name"], (
            f"Translation '{code}' name mismatch: "
            f"init.sql='{sql_trans['name']}', translations.py='{config['name']}'"
        )
        assert sql_trans["language"] == config["language"], (
            f"Translation '{code}' language mismatch: "
            f"init.sql='{sql_trans['language']}', translations.py='{config['language']}'"
        )
        assert sql_trans["language_code"] == config["language_code"], (
            f"Translation '{code}' language_code mismatch: "
            f"init.sql='{sql_trans['language_code']}', "
            f"translations.py='{config['language_code']}'"
        )

    # Verify no extra translations in init.sql
    for code in sql_translations:
        assert code in TRANSLATIONS, f"Translation '{code}' in init.sql but not in translations.py"
