-- CreateExtension
CREATE EXTENSION IF NOT EXISTS "plpgsql" WITH SCHEMA "pg_catalog" VERSION "1.0";

-- CreateExtension
CREATE EXTENSION IF NOT EXISTS "vector" WITH SCHEMA "public" VERSION "0.8.1";

-- CreateEnum
CREATE TYPE "event_type" AS ENUM ('INSTANCE_CREATED', 'INSTANCE_OPENED', 'INSTANCE_USED', 'INSTANCE_CLOSED', 'INSTANCE_ERROR', 'INSTANCE_HEARTBEAT', 'TASK_QUEUED', 'TASK_STARTED', 'TASK_COMPLETED', 'TASK_FAILED', 'TASK_RETRY', 'TASK_CANCELLED', 'TASK_TIMEOUT', 'DOCUMENT_CREATED', 'DOCUMENT_IMPORTED', 'DOCUMENT_EXPORTED', 'DOCUMENT_EDITED', 'DOCUMENT_DELETED', 'SYSTEM_STARTUP', 'SYSTEM_SHUTDOWN', 'WORKER_STARTED', 'WORKER_STOPPED');

-- CreateEnum
CREATE TYPE "instance_state" AS ENUM ('OPENING', 'OPEN', 'IDLE', 'IN_USE', 'CLOSING', 'CLOSED', 'ERROR', 'CRASHED');

-- CreateEnum
CREATE TYPE "task_priority" AS ENUM ('LOW', 'NORMAL', 'HIGH', 'CRITICAL');

-- CreateEnum
CREATE TYPE "task_state" AS ENUM ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'RETRYING', 'TIMEOUT');

-- CreateTable
CREATE TABLE "chapters" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "document_id" UUID NOT NULL,
    "title" TEXT NOT NULL,
    "order_index" INTEGER NOT NULL,
    "summary" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "chapters_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chunks" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "document_id" UUID NOT NULL,
    "chapter_id" UUID NOT NULL,
    "section_id" UUID NOT NULL,
    "page_id" UUID NOT NULL,
    "text" TEXT NOT NULL,
    "start_offset" INTEGER NOT NULL,
    "end_offset" INTEGER NOT NULL,
    "token_count" INTEGER NOT NULL DEFAULT 0,
    "embedding" vector,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "chunks_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "document_instances" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "document_id" UUID,
    "state" "instance_state" NOT NULL DEFAULT 'OPENING',
    "state_message" TEXT,
    "process_pid" INTEGER,
    "host_name" TEXT,
    "driver_type" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "opened_at" TIMESTAMPTZ(6),
    "last_used_at" TIMESTAMPTZ(6),
    "closed_at" TIMESTAMPTZ(6),
    "memory_mb" INTEGER,
    "cpu_percent" DOUBLE PRECISION,
    "file_path" TEXT,
    "metadata" JSONB NOT NULL DEFAULT '{}',

    CONSTRAINT "document_instances_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "documents" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "title" TEXT NOT NULL,
    "author" TEXT,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL,
    "source_file" BYTEA,
    "source_format" TEXT,
    "file_name" TEXT,

    CONSTRAINT "documents_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "execution_history" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "event_type" "event_type" NOT NULL,
    "event_message" TEXT,
    "document_id" UUID,
    "instance_id" UUID,
    "task_id" UUID,
    "timestamp" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "duration_ms" INTEGER,
    "actor_type" TEXT,
    "actor_id" TEXT,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "trace_id" TEXT,
    "parent_trace_id" TEXT,

    CONSTRAINT "execution_history_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "pages" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "section_id" UUID NOT NULL,
    "page_number" INTEGER NOT NULL,
    "content" TEXT NOT NULL DEFAULT '',
    "word_count" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "pages_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sections" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "chapter_id" UUID NOT NULL,
    "title" TEXT NOT NULL,
    "order_index" INTEGER NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "sections_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "task_queue" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "task_type" TEXT NOT NULL,
    "task_name" TEXT,
    "document_id" UUID,
    "instance_id" UUID,
    "parent_task_id" UUID,
    "payload" JSONB NOT NULL DEFAULT '{}',
    "result" JSONB,
    "state" "task_state" NOT NULL DEFAULT 'QUEUED',
    "priority" "task_priority" NOT NULL DEFAULT 'NORMAL',
    "max_retries" INTEGER NOT NULL DEFAULT 3,
    "retry_count" INTEGER NOT NULL DEFAULT 0,
    "retry_delay_seconds" INTEGER NOT NULL DEFAULT 5,
    "backoff_multiplier" DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "scheduled_for" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "started_at" TIMESTAMPTZ(6),
    "completed_at" TIMESTAMPTZ(6),
    "timeout_seconds" INTEGER NOT NULL DEFAULT 300,
    "error_message" TEXT,
    "error_stack" TEXT,
    "worker_id" TEXT,
    "worker_host" TEXT,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "tags" TEXT[] DEFAULT ARRAY[]::TEXT[],

    CONSTRAINT "task_queue_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "task_retries" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "task_id" UUID NOT NULL,
    "attempt_number" INTEGER NOT NULL,
    "started_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completed_at" TIMESTAMPTZ(6),
    "state" "task_state" NOT NULL,
    "error_message" TEXT,
    "error_stack" TEXT,
    "worker_id" TEXT,
    "worker_host" TEXT,
    "metadata" JSONB NOT NULL DEFAULT '{}',

    CONSTRAINT "task_retries_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_chapters_document" ON "chapters"("document_id" ASC);

-- CreateIndex
CREATE INDEX "idx_chapters_order" ON "chapters"("document_id" ASC, "order_index" ASC);

-- CreateIndex
CREATE INDEX "idx_chunks_chapter" ON "chunks"("chapter_id" ASC);

-- CreateIndex
CREATE INDEX "idx_chunks_document" ON "chunks"("document_id" ASC);

-- CreateIndex
CREATE INDEX "idx_chunks_page" ON "chunks"("page_id" ASC);

-- CreateIndex
CREATE INDEX "idx_instances_document" ON "document_instances"("document_id" ASC);

-- CreateIndex
CREATE INDEX "idx_instances_host" ON "document_instances"("host_name" ASC, "state" ASC);

-- CreateIndex
CREATE INDEX "idx_instances_last_used" ON "document_instances"("last_used_at" DESC);

-- CreateIndex
CREATE INDEX "idx_instances_state" ON "document_instances"("state" ASC);

-- CreateIndex
CREATE INDEX "idx_history_document" ON "execution_history"("document_id" ASC);

-- CreateIndex
CREATE INDEX "idx_history_event_type" ON "execution_history"("event_type" ASC);

-- CreateIndex
CREATE INDEX "idx_history_instance" ON "execution_history"("instance_id" ASC);

-- CreateIndex
CREATE INDEX "idx_history_task" ON "execution_history"("task_id" ASC);

-- CreateIndex
CREATE INDEX "idx_history_timestamp" ON "execution_history"("timestamp" DESC);

-- CreateIndex
CREATE INDEX "idx_history_trace" ON "execution_history"("trace_id" ASC);

-- CreateIndex
CREATE INDEX "idx_pages_order" ON "pages"("section_id" ASC, "page_number" ASC);

-- CreateIndex
CREATE INDEX "idx_pages_section" ON "pages"("section_id" ASC);

-- CreateIndex
CREATE INDEX "idx_sections_chapter" ON "sections"("chapter_id" ASC);

-- CreateIndex
CREATE INDEX "idx_sections_order" ON "sections"("chapter_id" ASC, "order_index" ASC);

-- CreateIndex
CREATE INDEX "idx_queue_created" ON "task_queue"("created_at" DESC);

-- CreateIndex
CREATE INDEX "idx_queue_document" ON "task_queue"("document_id" ASC);

-- CreateIndex
CREATE INDEX "idx_queue_instance" ON "task_queue"("instance_id" ASC);

-- CreateIndex
CREATE INDEX "idx_queue_parent" ON "task_queue"("parent_task_id" ASC);

-- CreateIndex
CREATE INDEX "idx_queue_priority" ON "task_queue"("priority" DESC, "created_at" ASC);

-- CreateIndex
CREATE INDEX "idx_queue_state" ON "task_queue"("state" ASC, "scheduled_for" ASC);

-- CreateIndex
CREATE INDEX "idx_retries_started" ON "task_retries"("started_at" DESC);

-- CreateIndex
CREATE INDEX "idx_retries_task" ON "task_retries"("task_id" ASC);

-- CreateIndex
CREATE UNIQUE INDEX "task_retries_task_id_attempt_number_key" ON "task_retries"("task_id" ASC, "attempt_number" ASC);

-- AddForeignKey
ALTER TABLE "chapters" ADD CONSTRAINT "chapters_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "documents"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chunks" ADD CONSTRAINT "chunks_chapter_id_fkey" FOREIGN KEY ("chapter_id") REFERENCES "chapters"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chunks" ADD CONSTRAINT "chunks_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "documents"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chunks" ADD CONSTRAINT "chunks_page_id_fkey" FOREIGN KEY ("page_id") REFERENCES "pages"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "chunks" ADD CONSTRAINT "chunks_section_id_fkey" FOREIGN KEY ("section_id") REFERENCES "sections"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "document_instances" ADD CONSTRAINT "document_instances_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "documents"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "execution_history" ADD CONSTRAINT "execution_history_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "documents"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "execution_history" ADD CONSTRAINT "execution_history_instance_id_fkey" FOREIGN KEY ("instance_id") REFERENCES "document_instances"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "execution_history" ADD CONSTRAINT "execution_history_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "task_queue"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "pages" ADD CONSTRAINT "pages_section_id_fkey" FOREIGN KEY ("section_id") REFERENCES "sections"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sections" ADD CONSTRAINT "sections_chapter_id_fkey" FOREIGN KEY ("chapter_id") REFERENCES "chapters"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_queue" ADD CONSTRAINT "task_queue_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "documents"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_queue" ADD CONSTRAINT "task_queue_instance_id_fkey" FOREIGN KEY ("instance_id") REFERENCES "document_instances"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_queue" ADD CONSTRAINT "task_queue_parent_task_id_fkey" FOREIGN KEY ("parent_task_id") REFERENCES "task_queue"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "task_retries" ADD CONSTRAINT "task_retries_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "task_queue"("id") ON DELETE CASCADE ON UPDATE CASCADE;

