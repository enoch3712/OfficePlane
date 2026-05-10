---
name: document-redact
description: Strip PII and sensitive entities from a document and store a redacted derivative.
inputs:
  - name: document_id
    type: string
    required: true
    description: UUID of the Document to redact.
  - name: entity_types
    type: array
    required: false
    description: Entity type filters to redact (e.g. ["PERSON", "EMAIL", "SSN"]). Defaults to all PII types.
  - name: output_format
    type: string
    required: false
    description: Format of the redacted derivative — "pdf" or "docx". Defaults to "pdf".
outputs:
  - name: redacted_document_id
    type: string
    description: UUID of the newly created redacted DocumentInstance.
  - name: redaction_count
    type: integer
    description: Number of entity spans replaced with redaction markers.
tools:
  - llm-redact
  - db-query
  - file-render
---

# document-redact

## When to use
Use this skill when the user needs a shareable version of a document with personal or
confidential information removed. Always run `document-classify` first so the sensitivity
tier is known; this skill reads that tier to determine which entity types to target by
default.

## How it works
- Fetch `Page` rows and their text content via `db-query`.
- Pass text in batches to `llm-redact` with the requested `entity_types`; receive spans
  to replace.
- Apply replacements and render the redacted output to file via `file-render`.
- Write a new `DocumentInstance` row pointing to the redacted file, linked to the source
  `Document`.
- Store a redaction manifest (count, entity types, page numbers) in the instance metadata.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EDITED` and `actor_type=agent`
after the redacted `DocumentInstance` row is committed.
