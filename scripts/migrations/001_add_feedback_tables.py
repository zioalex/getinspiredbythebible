#!/usr/bin/env python3
"""
Database migration: Add feedback and contact_submissions tables.

This migration creates tables for storing:
1. Message feedback (thumbs up/down ratings)
2. Contact form submissions

Run with: python scripts/migrations/001_add_feedback_tables.py
"""

import asyncio
import os
import sys

import asyncpg

# Add the api directory to the path for config access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from config import settings  # noqa: E402


async def run_migration():
    """Run the migration to create feedback tables."""
    print("Connecting to database...")

    # Parse connection string - handle both local and Azure formats
    database_url = settings.database_url
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(database_url)

    try:
        print("Creating feedback table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                message_id UUID NOT NULL,
                session_id VARCHAR(255),
                rating VARCHAR(10) NOT NULL CHECK (rating IN ('positive', 'negative')),
                comment TEXT,
                user_message TEXT,
                assistant_response TEXT,
                verses_cited JSONB,
                model_used VARCHAR(100),
                response_time_ms INTEGER
            );
        """)

        print("Creating feedback indexes...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_message_id ON feedback(message_id);
        """)

        print("Creating contact_submissions table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_submissions (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                email VARCHAR(255),
                subject VARCHAR(50) NOT NULL CHECK (
                    subject IN ('bug', 'feature', 'feedback', 'other')
                ),
                message TEXT NOT NULL,
                session_id VARCHAR(255),
                user_agent TEXT,
                status VARCHAR(20) DEFAULT 'new' CHECK (
                    status IN ('new', 'read', 'replied', 'resolved')
                )
            );
        """)

        print("Creating contact_submissions indexes...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contact_created_at ON contact_submissions(created_at);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_contact_status ON contact_submissions(status);
        """)

        print("Migration completed successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
