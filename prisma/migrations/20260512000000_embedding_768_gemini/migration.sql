-- Convert chunks.embedding column from 1536 to 768 dims (Gemini embedding-001).
-- Existing rows: 0 (chunks table is empty). Safe to drop+recreate.
ALTER TABLE chunks DROP COLUMN IF EXISTS embedding;
ALTER TABLE chunks ADD COLUMN embedding vector(768);

-- Create ivfflat index for cosine similarity search.
-- No ivfflat index existed previously (confirmed from baseline migration).
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
