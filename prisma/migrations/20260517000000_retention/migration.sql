CREATE TYPE disposition_action AS ENUM ('ARCHIVE', 'DESTROY', 'REVIEW');

CREATE TABLE IF NOT EXISTS retention_policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT UNIQUE NOT NULL,
    description     TEXT,
    duration_days   INTEGER NOT NULL,
    action          disposition_action NOT NULL DEFAULT 'REVIEW',
    start_trigger   TEXT NOT NULL DEFAULT 'created_at',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_retention_policy_name ON retention_policies(name);

CREATE TABLE IF NOT EXISTS document_retentions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    policy_id           UUID NOT NULL REFERENCES retention_policies(id) ON DELETE RESTRICT,
    start_at            TIMESTAMPTZ NOT NULL,
    disposition_due_at  TIMESTAMPTZ NOT NULL,
    legal_hold          BOOLEAN NOT NULL DEFAULT false,
    legal_hold_reason   TEXT,
    disposed            BOOLEAN NOT NULL DEFAULT false,
    disposed_at         TIMESTAMPTZ,
    actor               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, policy_id)
);
CREATE INDEX IF NOT EXISTS idx_doc_retention_doc ON document_retentions(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_retention_due ON document_retentions(disposition_due_at);
CREATE INDEX IF NOT EXISTS idx_doc_retention_hold ON document_retentions(legal_hold);

CREATE TABLE IF NOT EXISTS disposition_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retention_id UUID NOT NULL REFERENCES document_retentions(id) ON DELETE CASCADE,
    action       disposition_action NOT NULL,
    status       TEXT NOT NULL,
    reason       TEXT,
    actor        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_disposition_event_retention ON disposition_events(retention_id);
CREATE INDEX IF NOT EXISTS idx_disposition_event_created ON disposition_events(created_at);
