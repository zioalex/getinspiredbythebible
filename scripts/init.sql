-- PostgreSQL initialization script
-- Creates the pgvector extension and sets up the database

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable full-text search capabilities
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create indexes for better performance (tables created by SQLAlchemy)
-- These will be created after the initial data load
