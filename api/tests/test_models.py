"""
Tests for database models
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripture.models import Book, Verse


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
