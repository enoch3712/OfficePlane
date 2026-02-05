-- Migration: Add source file storage to documents table
-- Run this on existing databases to enable downloading original files

-- Add columns for storing the original uploaded file
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source_file BYTEA,
    ADD COLUMN IF NOT EXISTS source_format TEXT,
    ADD COLUMN IF NOT EXISTS file_name TEXT;

-- Add comment for documentation
COMMENT ON COLUMN documents.source_file IS 'Original uploaded file bytes (DOCX, PDF, etc.)';
COMMENT ON COLUMN documents.source_format IS 'Format of the source file (docx, pdf, doc)';
COMMENT ON COLUMN documents.file_name IS 'Original filename from upload';
