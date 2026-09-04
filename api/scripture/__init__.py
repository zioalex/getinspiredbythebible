"""
Scripture package - Bible data models, repository, and search.
"""

from .coverage import UnusableLanguage, check_translation_coverage, find_unusable_languages
from .database import DbSession, check_db_connection, close_db, get_db_session
from .models import Base, Book, Chapter, Passage, Topic, Verse
from .repository import ScriptureRepository
from .search import PassageResult, ScriptureSearchService, SearchResults, VerseResult

__all__ = [
    # Models
    "Book",
    "Chapter",
    "Verse",
    "Passage",
    "Topic",
    "Base",
    # Database
    "get_db_session",
    "DbSession",
    "check_db_connection",
    "close_db",
    # Repository
    "ScriptureRepository",
    # Search
    "ScriptureSearchService",
    "VerseResult",
    "PassageResult",
    "SearchResults",
    # Translation coverage diagnostics (BITB-054)
    "UnusableLanguage",
    "check_translation_coverage",
    "find_unusable_languages",
]
