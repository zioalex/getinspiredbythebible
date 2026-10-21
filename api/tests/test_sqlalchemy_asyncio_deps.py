"""Regression: SQLAlchemy 2.1 no longer pulls in greenlet implicitly.

The async engine needs it, so requirements.txt must install ``sqlalchemy[asyncio]``.
"""

from pathlib import Path


def test_greenlet_importable():
    import greenlet  # noqa: F401


def test_requirements_pin_asyncio_extra():
    reqs = (Path(__file__).resolve().parent.parent / "requirements.txt").read_text()
    assert "sqlalchemy[asyncio]" in reqs
