---
name: generate-pptx-blocks
description: Synthesise a PowerPoint (.pptx) deck from indexed OfficePlane source content using a typed block schema (title / text / table / image). Output is real bytes, not a hallucinated description.
inputs:
  - name: source_document_ids
    type: array
    required: true
    description: UUIDs of OfficePlane Document rows the agent should base the deck on.
  - name: brief
    type: string
    required: true
    description: One- to three-sentence instruction describing the deck's audience, length, and emphasis.
  - name: target_slide_count
    type: integer
    required: false
    description: Approximate slide count target. Defaults to 12.
outputs:
  - name: file_path
    type: string
    description: Absolute path on the server where the .pptx was written.
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

# generate-pptx-blocks

## When to use

Use this skill when the user asks for a PowerPoint deck derived from documents
ingested into OfficePlane — training overviews, executive readouts, course
introductions. Don't use it for raw transcription (use `document-export`) or for
Word documents (use `generate-docx-blocks`).

## How it works

1. Look up source documents in the `Document`/`Chapter`/`Section` Prisma tables.
   Use the per-document `summary`/`topics` to prime the prompt.
2. Ask DeepSeek (`flash` tier by default) to emit a strict block-based JSON document
   in the same shape as `course-document/SKILL.md`. The slide budget is
   `target_slide_count` (default 12). Each lesson should fit on 1-3 slides.
3. Parse the JSON into `BlocksDocument`. Reject blocks of unknown type.
4. Render via `python-pptx`. Each `title` block starts a new content slide; `text`
   blocks become bulleted body text; `table` blocks become PowerPoint tables; `image`
   blocks become inline pictures (when `object_key` resolves on disk).
5. Save bytes under `/data/workspaces/<job_id>/output.pptx`. Return `file_path`,
   `file_url`, `blocks_count`, and the originating `source_document_ids`.

## Audit

Emits `DOCUMENT_EXPORTED` with the originating `source_document_ids` in metadata.
`actor_type = "agent"`.
