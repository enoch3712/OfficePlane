---
name: document-summarize
description: Generate or refresh document, chapter, and section summaries top-down.
inputs:
  - name: document_id
    type: string
    required: true
    description: UUID of the Document to summarize.
  - name: depth
    type: string
    required: false
    description: Summary depth — "document", "chapter", or "section". Defaults to "document".
  - name: force_refresh
    type: boolean
    required: false
    description: Regenerate even if an existing summary is present. Defaults to false.
outputs:
  - name: summary
    type: string
    description: Top-level Document.summary text.
  - name: sections_updated
    type: integer
    description: Count of Chapter/Section rows that had their summary written or refreshed.
tools:
  - llm-summarize
  - db-query
---

# document-summarize

## When to use
Use this skill when the user wants a prose overview of a document, or when summaries are
stale after edits or re-ingestion. Prefer it over `document-search` when the user wants a
synthesis rather than source citations.

## How it works
- Load the `Document` row and its `Chapter` rows ordered by position via `db-query`.
- For each chapter, load `Section` rows; send page text from `Page` rows to `llm-summarize`
  bottom-up (section → chapter → document).
- Write results back to `Section.summary`, `Chapter.summary`, and `Document.summary`.
- Skip rows that already have summaries unless `force_refresh` is true.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EDITED` and `actor_type=agent`
after all summary writes are committed.
