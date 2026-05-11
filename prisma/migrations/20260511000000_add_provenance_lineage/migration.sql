-- CreateTable
CREATE TABLE "derivations" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "workspace_id" UUID NOT NULL,
    "generated_node_id" TEXT NOT NULL,
    "generated_doc_path" TEXT,
    "source_document_id" UUID,
    "source_chapter_id" UUID,
    "source_section_id" UUID,
    "page_numbers" INTEGER[] NOT NULL DEFAULT ARRAY[]::INTEGER[],
    "text_excerpt" TEXT,
    "skill" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "prompt_hash" TEXT,
    "confidence" DOUBLE PRECISION,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "derivations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "document_revisions" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "workspace_id" UUID NOT NULL,
    "parent_revision_id" UUID,
    "revision_number" INTEGER NOT NULL,
    "op" TEXT NOT NULL,
    "payload" JSONB NOT NULL DEFAULT '{}',
    "actor" TEXT,
    "snapshot_path" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "document_revisions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "skill_invocations" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "skill" TEXT NOT NULL,
    "model" TEXT,
    "workspace_id" UUID,
    "inputs" JSONB NOT NULL DEFAULT '{}',
    "outputs" JSONB NOT NULL DEFAULT '{}',
    "status" TEXT NOT NULL,
    "error_message" TEXT,
    "actor" TEXT,
    "started_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "duration_ms" INTEGER,
    "prompt_tokens" INTEGER,
    "completion_tokens" INTEGER,

    CONSTRAINT "skill_invocations_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_derivation_workspace" ON "derivations"("workspace_id");

-- CreateIndex
CREATE INDEX "idx_derivation_node" ON "derivations"("generated_node_id");

-- CreateIndex
CREATE INDEX "idx_derivation_source_doc" ON "derivations"("source_document_id");

-- CreateUniqueIndex
CREATE UNIQUE INDEX "uq_revision_workspace_n" ON "document_revisions"("workspace_id", "revision_number");

-- CreateIndex
CREATE INDEX "idx_revision_workspace" ON "document_revisions"("workspace_id");

-- CreateIndex
CREATE INDEX "idx_revision_parent" ON "document_revisions"("parent_revision_id");

-- CreateIndex
CREATE INDEX "idx_skill_inv_name" ON "skill_invocations"("skill");

-- CreateIndex
CREATE INDEX "idx_skill_inv_workspace" ON "skill_invocations"("workspace_id");

-- CreateIndex
CREATE INDEX "idx_skill_inv_started" ON "skill_invocations"("started_at");

-- AddForeignKey
ALTER TABLE "derivations" ADD CONSTRAINT "derivations_source_document_id_fkey" FOREIGN KEY ("source_document_id") REFERENCES "documents"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "document_revisions" ADD CONSTRAINT "document_revisions_parent_revision_id_fkey" FOREIGN KEY ("parent_revision_id") REFERENCES "document_revisions"("id") ON DELETE SET NULL ON UPDATE CASCADE;
