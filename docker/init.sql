-- OfficePlane Database Schema
-- PostgreSQL with pgvector for RAG memory

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Documents (Book-level)
-- ============================================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    author TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- Original file storage
    source_file BYTEA,
    source_format TEXT,
    file_name TEXT
);

-- ============================================================
-- Chapters
-- ============================================================
CREATE TABLE chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chapters_document ON chapters(document_id);
CREATE INDEX idx_chapters_order ON chapters(document_id, order_index);

-- ============================================================
-- Sections
-- ============================================================
CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sections_chapter ON sections(chapter_id);
CREATE INDEX idx_sections_order ON sections(chapter_id, order_index);

-- ============================================================
-- Pages
-- ============================================================
CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    word_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pages_section ON pages(section_id);
CREATE INDEX idx_pages_order ON pages(section_id, page_number);

-- ============================================================
-- Chunks (for RAG - sliding window embeddings)
-- ============================================================
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Denormalized references for fast filtering
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    section_id UUID NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    -- Chunk content
    text TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    token_count INTEGER DEFAULT 0,
    -- Vector embedding (OpenAI ada-002 = 1536 dimensions)
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vector similarity index (IVFFlat for speed at scale)
-- Use HNSW for smaller datasets: USING hnsw (embedding vector_cosine_ops)
CREATE INDEX chunks_embedding_idx ON chunks
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Fast lookups by document/chapter/page
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_chapter ON chunks(chapter_id);
CREATE INDEX idx_chunks_page ON chunks(page_id);

-- ============================================================
-- Helper Functions
-- ============================================================

-- Update timestamps automatically
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER chapters_updated_at
    BEFORE UPDATE ON chapters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER sections_updated_at
    BEFORE UPDATE ON sections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER pages_updated_at
    BEFORE UPDATE ON pages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- Vector Search Function
-- ============================================================
CREATE OR REPLACE FUNCTION search_chunks(
    query_embedding vector(1536),
    match_count INTEGER DEFAULT 5,
    filter_document_id UUID DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    chunk_text TEXT,
    page_id UUID,
    chapter_id UUID,
    document_id UUID,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.text AS chunk_text,
        c.page_id,
        c.chapter_id,
        c.document_id,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    WHERE (filter_document_id IS NULL OR c.document_id = filter_document_id)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
