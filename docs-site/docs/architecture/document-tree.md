---
sidebar_position: 5
title: The Document Tree
---

# The Document Tree

OfficePlane stores every document as a recursive tree of typed blocks. This page explains the shape of that tree, the block taxonomy, and why the design is aligned with public standards.

## Why a Recursive Tree?

Earlier versions of OfficePlane used a fixed three-level hierarchy — modules, lessons, and blocks — borrowed from LMS conventions. That schema had two problems:

1. **Depth mismatch.** Real documents vary: a legal brief may have parts, chapters, sections, sub-sections, and appendices. A slide deck may be flat. A fixed three-level hierarchy forces artificial nesting or flattens real structure.
2. **Vocabulary lock-in.** Terms like "lesson" signal a specific domain and complicate interoperability with document tooling outside that domain.

The replacement is a vocabulary-neutral recursive tree:

```
Document
└── Section (depth 0)
    └── Section (depth 1)
        └── ...
            └── Block  (leaf)
```

`Document → Section → Block` matches the structural primitives used by CommonMark, the Pandoc AST, and ProseMirror — the most widely deployed document processing tools in the open-source ecosystem. Using their vocabulary means OfficePlane can import from and export to those tools without lossy translation.

## The `Document → Section → Block` Shape

A `Document` is the root. It carries metadata and owns a list of top-level `Section` nodes. A `Section` can contain child `Section` nodes and/or leaf `Block` nodes. A `Block` is a typed, atomic piece of content.

```json
{
  "schema_version": "1.0",
  "id": "doc_01j2kqx8v",
  "title": "Q3 Engineering Review",
  "attributions": [
    {
      "source_doc_id": "doc_00xfabcd3",
      "source_section_id": "sec_intro_2",
      "relationship": "derived_from"
    }
  ],
  "sections": [
    {
      "id": "sec_01",
      "title": "Executive Summary",
      "depth": 0,
      "children": [],
      "blocks": [
        {
          "id": "blk_01",
          "type": "heading",
          "level": 1,
          "content": "Executive Summary"
        },
        {
          "id": "blk_02",
          "type": "paragraph",
          "content": "This report covers the quarter ending September 30."
        }
      ]
    },
    {
      "id": "sec_02",
      "title": "Infrastructure",
      "depth": 0,
      "children": [
        {
          "id": "sec_02_01",
          "title": "Database",
          "depth": 1,
          "children": [],
          "blocks": [
            {
              "id": "blk_10",
              "type": "table",
              "rows": [
                ["Metric", "Value"],
                ["p99 latency", "12 ms"],
                ["row count", "4.2 M"]
              ]
            }
          ]
        }
      ],
      "blocks": []
    }
  ]
}
```

Node `id` values are stable identifiers. All edit operations (insert, replace, delete) reference nodes by `id`, never by positional index. This makes edits composable and safe to apply out of order.

## Block Taxonomy

| `type` | Rendered in `.docx` | Rendered in `.pptx` |
|--------|---------------------|---------------------|
| `heading` | Word Heading style (level 1–6) | Slide title or section header text box |
| `paragraph` | Normal paragraph | Body text box |
| `list` | Bulleted or numbered list (via `ordered` flag) | Bulleted text box |
| `table` | Word table | Table shape |
| `figure` | Inline image + optional caption | Picture shape + caption text box |
| `code` | Monospace paragraph with border | Code text box (Courier New) |
| `callout` | Shaded paragraph with left border | Colored rectangle with inset text |
| `quote` | Block quote style | Italic text box with side rule |
| `divider` | Horizontal rule | Thin line shape |

The `level` field on `heading` maps directly to CommonMark ATX heading depth (`#` through `######`) and to `<h1>`–`<h6>` in HTML output.

## Alignment with Public Standards

| Standard | Alignment |
|----------|-----------|
| **CommonMark spec** | Block types match CommonMark leaf and container block taxonomy. `heading`, `paragraph`, `list`, `code`, `quote`, `divider` are 1:1 equivalents. |
| **Pandoc AST** | The tree shape (document → nested blocks) mirrors Pandoc's internal AST. Documents round-trip through `pandoc -f json` without structural loss. |
| **ProseMirror** | Block types correspond to ProseMirror node types. A ProseMirror schema can be derived directly from the block taxonomy, enabling browser-side rich-text editing. |
| **OOXML (DOCX/PPTX)** | The renderer maps each block type to the corresponding OOXML element (`w:p`, `w:tbl`, `a:pic`, etc.). No intermediate format needed. |

## Schema Versioning

The `schema_version` field at the document root is a semver string. Breaking changes to the block taxonomy or tree structure increment the major version. The API always returns the version it stored; upgrade migrations are applied lazily on read.

## `attributions` Array

Every `Document` carries a top-level `attributions` array. Each entry records a relationship to a source document or section:

```json
{
  "source_doc_id": "doc_00xfabcd3",
  "source_section_id": "sec_intro_2",
  "relationship": "derived_from",
  "agent_run_id": "run_xyz"
}
```

`relationship` is an open enum; current values are `derived_from`, `quoted_from`, and `merged_from`. This array is the entry point for the provenance graph described in [Source Trail: Provenance & Lineage](/architecture/provenance-and-lineage).
