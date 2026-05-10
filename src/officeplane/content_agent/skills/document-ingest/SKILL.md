---
name: document-ingest
description: Upload, vision-parse, and persist a document with multi-level summaries.
inputs:
  - name: file_path
    type: string
    required: true
    description: Local or remote path to the source file.
  - name: filename
    type: string
    required: true
    description: Human-readable filename stored in the Document record.
  - name: collection_id
    type: string
    required: false
    description: Optional folder/collection to assign the document to on creation.
outputs:
  - name: document_id
    type: string
    description: UUID of the newly created Document row.
  - name: page_count
    type: integer
    description: Number of pages parsed from the document.
tools:
  - vision-parse
  - db-query
---

# document-ingest

## When to use
Pick this skill when the user uploads a file or references a path that has not yet been
imported into the system. Use it before any classify, summarize, or extract operation
because those skills assume the document already exists in the store.

## How it works
- Convert the source file to images via `vision-parse` (DOCX → PDF → per-page images).
- Send page images in batches to the vision model; receive a structured JSON outline.
- Write one `Document` row, one `Chapter` row per chapter, one `Section` per section,
  and one `Page` per page to the DB via `db-query`.
- Chunk page text and write `Chunk` rows; optionally embed and store vectors.
- Compute top-down `Document.summary`, `Chapter.summary`, and `Section.summary`.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_IMPORTED` and `actor_type=agent`
after the `Document` row is committed.
