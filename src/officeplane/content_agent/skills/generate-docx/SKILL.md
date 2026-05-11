---
name: generate-docx
description: Generate a Word document from ingested source documents using the agnostic Document tree (CommonMark/Pandoc-aligned)
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  source_document_ids:
    type: list[str]
    required: true
    description: Prisma Document.id values to ground generation in
  brief:
    type: str
    required: true
    description: What the user wants generated
  style:
    type: str
    required: false
    description: Tone/style hint (e.g. "clinical", "casual", "technical")
  audience:
    type: str
    required: false
    description: Target reader description
  target_length:
    type: str
    required: false
    description: "short | medium | long (default: medium)"
outputs:
  file_path: str
  file_url: str
  title: str
  node_count: int
  model: str
  source_document_ids: list[str]
---

# generate-docx

Generates a Microsoft Word (`.docx`) document from one or more ingested
source documents stored in the OfficePlane database.

## What it does

1. Loads the requested source documents from Postgres via Prisma (chapters,
   sections, summaries).
2. Prompts DeepSeek v4-flash to produce a **agnostic Document JSON tree**
   aligned to the CommonMark / Pandoc AST vocabulary — NOT the legacy
   `modules → lessons → blocks` schema.
3. Parses the JSON into a `Document` dataclass tree via `parse_document`.
4. Renders the tree to `.docx` bytes via `render_docx`.
5. Writes the result to `/data/workspaces/<job_id>/output.docx`.

## Expected JSON shape

The LLM must return a strict JSON object conforming to the agnostic Document
schema:

```json
{
  "type": "document",
  "schema_version": "1.0",
  "meta": {"title": "My Document", "language": "en"},
  "children": [
    {
      "type": "section",
      "id": "s1",
      "level": 1,
      "heading": "Introduction",
      "children": [
        {"type": "paragraph", "text": "Opening prose here."},
        {
          "type": "list",
          "ordered": false,
          "items": [
            {"type": "paragraph", "text": "First bullet"},
            {"type": "paragraph", "text": "Second bullet"}
          ]
        }
      ]
    }
  ],
  "attributions": [
    {
      "node_id": "s1",
      "document_id": "<source-doc-uuid>",
      "section_id": "<source-section-id>"
    }
  ]
}
```

Key rules:
- Sections nest recursively. Use `level` 1..6 to indicate depth.
- Block types: `heading`, `paragraph`, `list`, `table`, `figure`, `code`,
  `callout`, `quote`, `divider`.
- **Never** emit `"modules"` or `"lessons"` — use nested sections instead.
- Every non-trivial node should have an `id` (short string).
- Provide at least one attribution per major section pointing back to a
  source `document_id`.

## Minimal output example

```json
{
  "type": "document",
  "meta": {"title": "BP Primer"},
  "children": [
    {
      "type": "section",
      "id": "intro",
      "level": 1,
      "heading": "Why Measure Blood Pressure",
      "children": [
        {"type": "paragraph", "text": "Early detection of hypertension saves lives."}
      ]
    }
  ],
  "attributions": [
    {"node_id": "intro", "document_id": "doc-abc123"}
  ]
}
```
