CREATE TYPE trigger_status AS ENUM ('ENABLED', 'DISABLED');

CREATE TABLE IF NOT EXISTS triggers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    description   TEXT,
    event_type    TEXT NOT NULL,
    filter        JSONB NOT NULL DEFAULT '{}',
    pipeline_spec JSONB NOT NULL DEFAULT '{}',
    status        trigger_status NOT NULL DEFAULT 'ENABLED',
    actor         TEXT,
    fire_count    INTEGER NOT NULL DEFAULT 0,
    last_fired_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_trigger_event_type ON triggers(event_type);
CREATE INDEX IF NOT EXISTS idx_trigger_status ON triggers(status);

CREATE TABLE IF NOT EXISTS event_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type          TEXT NOT NULL,
    payload             JSONB NOT NULL DEFAULT '{}',
    source              TEXT,
    matched_trigger_ids TEXT[] NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_created ON event_logs(created_at);
