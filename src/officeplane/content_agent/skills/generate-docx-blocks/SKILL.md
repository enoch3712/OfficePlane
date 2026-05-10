---
name: generate-docx-blocks
description: Synthesise a Microsoft Word (.docx) document from indexed OfficePlane source content using a typed block schema (title / text / table / image). Output is real bytes, not a hallucinated description.
inputs:
  - name: source_document_ids
    type: array
    required: true
    description: UUIDs of OfficePlane Document rows the agent should base the output on.
  - name: brief
    type: string
    required: true
    description: One- to three-sentence instruction describing what the generated docx should cover and for whom.
  - name: target_length
    type: string
    required: false
    description: One of "short" (~1 page), "medium" (3-5 pages), "long" (10+ pages). Defaults to "medium".
outputs:
  - name: file_path
    type: string
    description: Absolute path on the server where the .docx was written (under /data/workspaces).
  - name: file_url
    type: string
    description: Relative URL the UI can use to download it.
  - name: blocks_count
    type: integer
  - name: source_document_ids
    type: array
tools:
  - db-query
  - llm-generate
---

# generate-docx-blocks

## When to use

Use this skill when the user asks for a Word document derived from documents already
ingested into OfficePlane — summaries, hand-outs, course-leader notes, executive briefs,
etc. Do NOT use it for raw transcription (use `document-export`) or for slides
(use `generate-pptx-blocks`).

## How it works

1. Look up the source documents via the `Document`/`Chapter`/`Section` Prisma tables.
   Use the per-document `summary`/`topics` to prime the prompt and the chapter titles
   to give the LLM a content map.
2. Ask DeepSeek (`flash` tier by default) to emit a strict block-based JSON document
   following the schema in `course-document/SKILL.md`: modules → lessons → blocks.
3. Parse the JSON into the `BlocksDocument` typed model. Reject blocks of unknown type.
4. Render via `python-docx`: titles → Heading 3, text → Paragraph, table → Table,
   image → InlinePicture. Citations from `source_references` are rendered as small
   italicised grey footnote runs after each block.
5. Save bytes under `/data/workspaces/<job_id>/output.docx`. Return `file_path`,
   `file_url`, `blocks_count`, and the originating `source_document_ids`.

## Audit

Emits `DOCUMENT_EXPORTED` event with the generated document_id (if persisted) and
the source_document_ids list in the metadata. `actor_type = "agent"`.
