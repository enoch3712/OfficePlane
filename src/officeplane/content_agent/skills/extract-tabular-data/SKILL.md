---
name: extract-tabular-data
description: Walk an ingested document's pages and extract every detected table into a canonical {name, headers, rows} structure with source attributions
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: document_id
    type: str
    required: true
    description: Prisma Document.id (any format — PDF/DOCX/PPTX/XLSX)
  - name: max_tables
    type: int
    required: false
    description: Soft cap on number of tables to return (default 20)
  - name: hint
    type: str
    required: false
    description: Optional context to focus extraction — e.g. "financial figures only" or "patient measurements"
outputs:
  - name: document_id
    type: str
  - name: title
    type: str
  - name: table_count
    type: int
  - name: tables
    type: list[dict]
    description: "[{name, headers, rows, source_page, attribution: {document_id, section_id, page_numbers}}]"
  - name: model
    type: str
---

# extract-tabular-data

Walks every page of any ingested OfficePlane document (PDF, DOCX, PPTX, XLSX) and
extracts all detected tables into a canonical structured format ready for downstream
structured consumers such as Excel population (Phase 37).

## How it works

1. Fetches the document record from the database using `document_id`. Works with any
   format — not restricted to Excel.
2. Walks the chapter → section → page hierarchy produced by the ingestion pipeline,
   collecting up to 6 000 characters per page. Falls back to a flat page list for
   documents ingested with older pipelines.
3. Assembles all page content into a single prompt blob with page-number and
   section-title markers, then sends it to DeepSeek (`OFFICEPLANE_AGENT_MODEL_FLASH`,
   default `deepseek/deepseek-v4-flash`) with `temperature=0` and
   `response_format={"type": "json_object"}` for deterministic output.
4. Normalises every table returned by the model:
   - Tables with no `headers` list or no `rows` list are silently dropped.
   - Each row is padded with `null` or truncated to match the header width.
   - Tables with no valid rows after normalisation are dropped.
   - The output list is hard-capped at `max_tables`.
5. Builds an `attribution` block for each table containing `document_id`,
   `section_id`, and `page_numbers` so downstream consumers can trace data back to
   its source page.
6. Writes a `SkillInvocation` audit row via `persist_skill_invocation`.

## Extraction prompt rules

The model is instructed to:

- **Not invent rows** — only include data literally present in the source pages.
- **Coerce numbers** — strings like `"1,200"` become `1200`; `"12.5%"` becomes
  `0.125`.
- **Normalise dates** — date-like strings are kept as ISO-8601 (`"YYYY-MM-DD"`)
  when the conversion is unambiguous.
- **Infer headers** — when a table has no explicit header row the model derives
  column names from surrounding context or assigns generic labels (`Col1`, `Col2`, …).
- **Skip trivially small tables** — tables with fewer than 2 data rows are omitted
  unless they are clearly a standalone summary block.
- **Name each table** — a short descriptive name (≤ 60 characters) that distils the
  table's purpose is required for every extracted table.
- **Classify column types** — each column is tagged as `"text"`, `"number"`,
  `"date"`, `"percent"`, or `null` when type cannot be determined.

The optional `hint` input narrows extraction focus, e.g. `"financial figures only"`
or `"patient measurements"`. The model is instructed to skip tables that do not
match the hint.

## Output shape

```json
{
  "document_id": "cuid...",
  "title": "Q3 Sales Report",
  "table_count": 2,
  "tables": [
    {
      "name": "Regional Revenue by Quarter",
      "headers": ["Region", "Q1", "Q2", "Q3"],
      "rows": [
        ["North America", 1200000, 1350000, 1480000],
        ["Europe",         900000,  980000, 1050000]
      ],
      "source_page": 3,
      "row_count": 2,
      "column_types": ["text", "number", "number", "number"],
      "attribution": {
        "document_id": "cuid...",
        "section_id": "sec-uuid...",
        "page_numbers": [3]
      }
    }
  ],
  "model": "deepseek/deepseek-v4-flash"
}
```

If the document has no page content the skill returns early with `table_count=0`,
`tables=[]`, and a `note` field explaining the situation.
