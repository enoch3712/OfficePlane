---
name: document-extract
description: Extract structured fields from a document using a caller-supplied JSON schema.
inputs:
  - name: document_id
    type: string
    required: true
    description: UUID of the Document to extract from.
  - name: schema
    type: object
    required: true
    description: JSON Schema object describing the fields to extract (e.g. contract parties, dates, amounts).
  - name: page_range
    type: array
    required: false
    description: Optional [start, end] page numbers to limit extraction scope.
outputs:
  - name: extracted
    type: object
    description: Key-value map of extracted fields matching the caller-supplied schema.
  - name: confidence
    type: object
    description: Per-field confidence scores (0.0–1.0).
tools:
  - llm-extract
  - db-query
---

# document-extract

## When to use
Use this skill when the user needs structured data pulled from a specific document — such
as contract terms, invoice line items, or form fields. Prefer it over `document-search`
when the output must conform to a known schema rather than returning ranked snippets.

## How it works
- Load `Page` rows (optionally scoped by `page_range`) and join with `Section` context
  via `db-query`.
- Serialize page text and pass it alongside the caller's JSON Schema to `llm-extract`.
- The model returns a JSON object; validate it against the schema before returning.
- Persist a snapshot of the extracted payload to the `Document.metadata` field via
  `db-query` for audit trail.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EDITED` and `actor_type=agent`.
