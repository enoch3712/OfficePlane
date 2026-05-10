---
name: document-relate
description: Create or query directed relations between documents as graph edges.
inputs:
  - name: document_id
    type: string
    required: true
    description: UUID of the source Document.
  - name: relation_type
    type: string
    required: true
    description: Relation label — e.g. "supersedes", "references", "derived-from", "related-to".
  - name: target_document_id
    type: string
    required: false
    description: UUID of the target Document. Required for "create"; omit to query existing relations.
  - name: action
    type: string
    required: false
    description: One of "create" or "query". Defaults to "query".
outputs:
  - name: relations
    type: array
    description: List of {relation_id, relation_type, target_document_id, target_title} for the source document.
  - name: relation_id
    type: string
    description: UUID of the newly created relation row; populated for "create" action only.
tools:
  - db-query
---

# document-relate

## When to use
Invoke this skill when the user says a document supersedes, references, or is derived from
another, or when they ask which documents are related to a given one. Use it to build the
knowledge graph before running `document-search` over a topic cluster.

## How it works
- For "create": validate that both `Document` rows exist via `db-query`, then insert a
  relation edge into the document relations join table linked to both `Document` UUIDs.
- For "query": fetch all outbound and inbound relation edges for `document_id` from the
  relations table; enrich each with the related `Document.title` via `db-query`.
- Enforce that no duplicate (source, type, target) triplet is inserted.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EDITED` and `actor_type=agent`
for "create". The "query" action is read-only and emits no row.
