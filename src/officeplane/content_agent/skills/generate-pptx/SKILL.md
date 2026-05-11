---
name: generate-pptx
description: Generate a PowerPoint deck from ingested source documents using the agnostic Document tree (parametrised by slide_count, style, audience, tone)
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  source_document_ids:
    type: list[str]
    required: true
  brief:
    type: str
    required: true
  slide_count:
    type: int
    required: false
    default: 10
    description: Target number of slides (soft cap — renderer truncates)
  style:
    type: str
    required: false
    default: professional
    description: e.g. "clinical", "corporate", "casual", "academic"
  audience:
    type: str
    required: false
    default: general
  tone:
    type: str
    required: false
    default: neutral
    description: e.g. "warm", "concise", "authoritative"
outputs:
  file_path: str
  file_url: str
  title: str
  slide_count: int
  model: str
  source_document_ids: list[str]
---

# generate-pptx

Generates a PowerPoint (`.pptx`) deck from one or more ingested source
documents stored in the OfficePlane database.

## What it does

1. Loads the requested source documents from Postgres via Prisma (chapters,
   sections, summaries).
2. Prompts the LLM to produce an **agnostic Document JSON tree** aligned to
   the CommonMark / Pandoc AST vocabulary — NOT the legacy
   `modules → lessons → blocks` schema.
3. Parses the JSON into a `Document` dataclass tree via `parse_document`.
4. Forces `doc.meta.render_hints["max_slides"] = slide_count` so the renderer
   hard-truncates if the LLM overshot.
5. Renders the tree to `.pptx` bytes via `render_pptx`.
6. Writes the result to `/data/workspaces/<job_id>/output.pptx`.

## Slide layout strategy

The renderer maps the document tree to slides as follows:

- **Title slide** — always first if `doc.meta.title` is non-empty.
- **Section divider slide** — for every level-1 Section that has child Sections
  beneath it (produced by `_LAYOUT_SECTION_HEADER`).
- **Content slide** — for every leaf-bearing section (a Section whose children
  contain at least one non-Section block). Batches heading / paragraph / list /
  callout / quote / divider blocks into a single slide body.
- **Big-primitive slides** — Table, Figure, or Code blocks each get their own
  dedicated slide to avoid crowding.

Plan the section nesting depth and branching factor so the total slide count
(title + dividers + content + big-primitives) stays close to `slide_count`.

## Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `slide_count` | `10` | Renderer hard-truncates to this cap |
| `style` | `professional` | Visual/verbal register: clinical, corporate, casual, academic |
| `audience` | `general` | Who will view the deck |
| `tone` | `neutral` | Voice: warm, concise, authoritative, etc. |

## Expected JSON shape

```json
{
  "type": "document",
  "schema_version": "1.0",
  "meta": {
    "title": "My Deck",
    "language": "en",
    "render_hints": {"max_slides": 10}
  },
  "children": [
    {
      "type": "section",
      "id": "s1",
      "level": 1,
      "heading": "Introduction",
      "children": [
        {"type": "paragraph", "text": "Opening bullet."},
        {
          "type": "list",
          "ordered": false,
          "items": [
            {"type": "paragraph", "text": "Key point one"},
            {"type": "paragraph", "text": "Key point two"}
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
- Each content slide should have at most 6 bullet items.
- Headings must be 60 characters or fewer; bullets 18 words or fewer.
- **Never** emit `"modules"` or `"lessons"` — use nested sections instead.
- Every non-trivial node should have an `id` (short string).
- Provide at least one attribution per major section pointing back to a
  source `document_id`.
