-- Enum
CREATE TYPE document_status AS ENUM ('DRAFT', 'REVIEW', 'APPROVED', 'ARCHIVED');

-- Document status column (default DRAFT applies to existing rows automatically)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS status document_status NOT NULL DEFAULT 'DRAFT';

-- Status event audit table
CREATE TABLE IF NOT EXISTS document_status_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    from_status  document_status,
    to_status    document_status NOT NULL,
    actor        TEXT,
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_status_event_document ON document_status_events(document_id);
CREATE INDEX IF NOT EXISTS idx_status_event_created  ON document_status_events(created_at);
