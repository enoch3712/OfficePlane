-- Drop FK references first so the column drops don't cascade-fail
ALTER TABLE task_queue DROP COLUMN IF EXISTS instance_id;
ALTER TABLE execution_history DROP COLUMN IF EXISTS instance_id;

-- Now safe to drop the parent table
DROP TABLE IF EXISTS document_instances;

-- Drop the enum (after the table that used it)
DROP TYPE IF EXISTS instance_state;
