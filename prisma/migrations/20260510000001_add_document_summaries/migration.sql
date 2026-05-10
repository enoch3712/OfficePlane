-- AlterTable
ALTER TABLE "documents" ADD COLUMN     "key_entities" JSONB NOT NULL DEFAULT '{}',
ADD COLUMN     "summarized_at" TIMESTAMPTZ,
ADD COLUMN     "summary" TEXT,
ADD COLUMN     "summary_model" TEXT,
ADD COLUMN     "topics" TEXT[] DEFAULT ARRAY[]::TEXT[];

-- AlterTable
ALTER TABLE "sections" ADD COLUMN     "summary" TEXT;
