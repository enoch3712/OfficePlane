---
name: generate-from-collection
description: Generate a single Document (Word/PowerPoint) from all source documents in a collection, with attributions back to each source
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: collection_id
    type: str
    required: false
    description: Prisma Collection.id — pulls all member documents
  - name: source_document_ids
    type: list[str]
    required: false
    description: Explicit document_ids (alternative to collection_id)
  - name: brief
    type: str
    required: true
  - name: format
    type: str
    required: false
    description: "docx | pptx (default: docx)"
  - name: style
    type: str
    required: false
  - name: audience
    type: str
    required: false
  - name: tone
    type: str
    required: false
  - name: slide_count
    type: int
    required: false
    description: Only used when format=pptx
outputs:
  - name: file_path
    type: str
  - name: file_url
    type: str
  - name: title
    type: str
  - name: model
    type: str
  - name: format
    type: str
  - name: source_document_count
    type: int
  - name: source_document_ids
    type: list[str]
---

# generate-from-collection

The "wrap a folder" entry point for OfficePlane content generation. Picks up
every document that belongs to a Collection (or an explicit list of document
IDs) and synthesises them into **one** combined Word or PowerPoint output with
per-node attributions pointing back to whichever source each piece of content
was drawn from.

## Why this skill exists

`generate-docx` and `generate-pptx` both require the caller to supply
`source_document_ids` manually. When users have already organised their source
material into a Collection (a folder-like grouping created by the
`collection-manage` skill or the ECM UI), they should be able to say
"generate a deck from this collection" without enumerating every member ID.
`generate-from-collection` wraps that lookup and then does the same
LLM-grounded generation, with all attributions intact.

## How attributions are emitted

Each major section in the output document includes one or more attribution
objects of the form:

```json
{
  "node_id": "<generated-node-id>",
  "document_id": "<source-uuid>",
  "section_id": "<source-section-uuid>",
  "page_numbers": [1, 2]
}
```

A single section may attribute to multiple sources if it synthesises
content from more than one input document. The attributions are persisted
to the `Derivation` table by `persist_derivations_from_document` so they
can be retrieved via the lineage API (`GET /api/lineage/workspace/{id}`).

## Inputs

| Name | Required | Notes |
|------|----------|-------|
| `collection_id` | one of these | Prisma `Collection.id` |
| `source_document_ids` | one of these | Explicit list of Document IDs |
| `brief` | yes | What the combined document should cover |
| `format` | no | `docx` (default) or `pptx` |
| `style` | no | e.g. `professional`, `clinical`, `casual` |
| `audience` | no | Target reader |
| `tone` | no | e.g. `neutral`, `authoritative`, `warm` |
| `slide_count` | no | Target slides when `format=pptx` (default 10) |

## Example invocation

```bash
curl -X POST http://localhost:8001/api/jobs/invoke/generate-from-collection \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "collection_id": "col-abc123",
      "brief": "Executive overview of our AI compliance training materials",
      "format": "pptx",
      "slide_count": 8,
      "audience": "C-suite",
      "tone": "authoritative"
    }
  }'
```

Or with explicit IDs instead of a collection:

```bash
curl -X POST http://localhost:8001/api/jobs/invoke/generate-from-collection \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "source_document_ids": ["d0a5322e-e48b-4fcc-974c-cc246fcac65b", "..."],
      "brief": "Consolidated training guide",
      "format": "docx"
    }
  }'
```

## Output

```json
{
  "skill": "generate-from-collection",
  "output": {
    "file_path": "/data/workspaces/<job_id>/output.pptx",
    "file_url": "/data/workspaces/<job_id>/output.pptx",
    "title": "AI Compliance Training Overview",
    "model": "deepseek/deepseek-v4-flash",
    "format": "pptx",
    "source_document_count": 4,
    "source_document_ids": ["uuid1", "uuid2", "uuid3", "uuid4"],
    "slide_count": 8
  }
}
```

## View source trail

After generation the lineage endpoint shows which nodes came from which
sources:

```
GET /api/lineage/workspace/<job_id>
```
