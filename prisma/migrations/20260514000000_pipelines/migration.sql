CREATE TYPE pipeline_run_state AS ENUM ('QUEUED', 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED');

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT,
    spec          JSONB NOT NULL DEFAULT '{}',
    state         pipeline_run_state NOT NULL DEFAULT 'QUEUED',
    parameters    JSONB NOT NULL DEFAULT '{}',
    actor         TEXT,
    error_message TEXT,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_state ON pipeline_runs(state);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_started ON pipeline_runs(started_at);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_index    INTEGER NOT NULL,
    alias         TEXT,
    skill         TEXT NOT NULL,
    inputs        JSONB NOT NULL DEFAULT '{}',
    outputs       JSONB NOT NULL DEFAULT '{}',
    state         pipeline_run_state NOT NULL DEFAULT 'QUEUED',
    error_message TEXT,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    duration_ms   INTEGER,
    UNIQUE (run_id, step_index)
);
CREATE INDEX IF NOT EXISTS idx_pipeline_step_run ON pipeline_steps(run_id);
