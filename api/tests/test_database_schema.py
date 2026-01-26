"""
Tests for database schema validation.

These tests ensure the database schema matches the multilingual requirements.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripture.models import Book, Chapter, Translation, Verse


def test_translation_table_exists():
    """Test that Translation model has all required fields"""
    assert hasattr(Translation, "code")
    assert hasattr(Translation, "name")
    assert hasattr(Translation, "language")
    assert hasattr(Translation, "language_code")
    assert hasattr(Translation, "is_default")
    assert hasattr(Translation, "verses")


def test_verse_has_translation_column():
    """Test that Verse model has translation field"""
    assert hasattr(Verse, "translation")
    assert hasattr(Verse, "translation_rel")


def test_verse_table_constraints():
    """Test that Verse model has correct unique constraint"""
    # Get the table args
    table_args = Verse.__table_args__

    # Should contain a UniqueConstraint with translation field
    has_translation_constraint = False
    for arg in table_args:
        if hasattr(arg, "name") and arg.name == "unique_verse_translation":
            has_translation_constraint = True
            # Verify it includes the translation column
            column_names = [col.name for col in arg.columns]
            assert (
                "translation" in column_names
            ), "unique_verse_translation constraint missing translation column"
            assert "book_id" in column_names
            assert "chapter_number" in column_names
            assert "verse_number" in column_names

    assert has_translation_constraint, "Missing unique_verse_translation constraint"


def test_verse_default_translation():
    """Test that Verse translation field has kjv default"""
    # Check the column definition
    translation_col = Verse.__table__.columns["translation"]
    assert translation_col.default is not None, "translation column should have a default value"
    # The default is a ColumnDefault object, check its arg
    assert translation_col.default.arg == "kjv", "translation column default should be 'kjv'"


def test_book_table_exists():
    """Test that Book model has all required fields"""
    assert hasattr(Book, "id")
    assert hasattr(Book, "name")
    assert hasattr(Book, "abbreviation")
    assert hasattr(Book, "testament")
    assert hasattr(Book, "position")


def test_chapter_table_exists():
    """Test that Chapter model has all required fields"""
    assert hasattr(Chapter, "id")
    assert hasattr(Chapter, "book_id")
    assert hasattr(Chapter, "number")


def test_verse_relationships():
    """Test that Verse has correct relationships"""
    assert hasattr(Verse, "book")
    assert hasattr(Verse, "chapter")
    assert hasattr(Verse, "translation_rel")
