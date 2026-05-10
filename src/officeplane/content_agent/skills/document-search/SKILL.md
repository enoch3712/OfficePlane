---
name: document-search
description: Hybrid vector + full-text search across the document store with hierarchical context.
inputs:
  - name: query
    type: string
    required: true
    description: Natural-language question or keywords to search for.
  - name: top_k
    type: integer
    required: false
    description: Maximum number of chunks to return. Defaults to 8.
  - name: collection_id
    type: string
    required: false
    description: Optional collection scope.
outputs:
  - name: results
    type: array
    description: Ranked list of {chunk_id, document_id, document_title, chapter_title, section_title, score, snippet}.
tools:
  - vector-search
  - db-query
---

# document-search

## When to use
Pick this skill when the user asks a semantic question that may be answered by indexed
content. Prefer it over `document-extract` for retrieval; prefer it over `document-summarize`
when the user wants citations rather than a synthesis.

## How it works
- First inspect `Document.summary` and `Document.topics` to shortlist candidate documents.
- Run pgvector cosine similarity against the `Chunk.embedding` column via `vector-search`.
- Enrich top-k chunks with their `Chapter.title` and `Section.title` via `db-query`.
- Apply `collection_id` scoping if provided.

## Audit
Emits no `ExecutionHistory` rows (read-only). Each call may still produce a structured log line for observability.
