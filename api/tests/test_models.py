"""
Tests for database models
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripture.models import Book, Translation, Verse


def test_book_model_creation():
    """Test Book model can be instantiated"""
    book = Book(name="Genesis", abbreviation="Gen", testament="old", position=1)
    assert book.name == "Genesis"
    assert book.testament == "old"
    assert book.position == 1


def test_verse_model_creation():
    """Test Verse model can be instantiated"""
    # Note: book_id and chapter_id are foreign keys
    verse = Verse(
        book_id=1,
        chapter_id=1,
        chapter_number=1,
        verse_number=1,
        text="In the beginning God created the heaven and the earth.",
    )
    assert verse.book_id == 1
    assert verse.chapter_number == 1
    assert verse.verse_number == 1
    assert "beginning" in verse.text


def test_verse_model_with_translation():
    """Test Verse model with translation field"""
    verse = Verse(
        book_id=1,
        chapter_id=1,
        chapter_number=1,
        verse_number=1,
        text="In the beginning God created the heaven and the earth.",
        translation="kjv",
    )
    assert verse.translation == "kjv"
    assert verse.book_id == 1
    assert verse.chapter_number == 1


def test_verse_model_italian():
    """Test Verse model with Italian translation"""
    verse = Verse(
        book_id=1,
        chapter_id=1,
        chapter_number=1,
        verse_number=1,
        text="Nel principio Iddio creò i cieli e la terra.",
        translation="ita1927",
    )
    assert verse.translation == "ita1927"
    assert "principio" in verse.text


def test_translation_model_creation():
    """Test Translation model can be instantiated"""
    translation = Translation(
        code="kjv",
        name="King James Version",
        language="English",
        language_code="en",
        description="Classic English translation from 1611",
        is_default=True,
    )
    assert translation.code == "kjv"
    assert translation.name == "King James Version"
    assert translation.language == "English"
    assert translation.language_code == "en"
    assert translation.is_default is True


def test_translation_model_italian():
    """Test Translation model with Italian translation"""
    translation = Translation(
        code="ita1927",
        name="Riveduta 1927",
        language="Italian",
        language_code="it",
        description="Italian Luzzi translation from 1927",
        is_default=False,
    )
    assert translation.code == "ita1927"
    assert translation.language == "Italian"
    assert translation.language_code == "it"
    assert translation.is_default is False


def test_translation_model_german():
    """Test Translation model with German translation"""
    translation = Translation(
        code="schlachter",
        name="Schlachter 1951",
        language="German",
        language_code="de",
    )
    assert translation.code == "schlachter"
    assert translation.language == "German"
    assert translation.language_code == "de"
