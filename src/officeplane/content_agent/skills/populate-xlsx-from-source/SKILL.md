---
name: populate-xlsx-from-source
description: Extract tabular data from one or more source documents and populate a saved xlsx template — composes extract-tabular-data + xlsx-template-apply
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: source_document_ids
    type: list[str]
    required: true
    description: Prisma Document.id values to extract tables from (PDF/DOCX/PPTX/XLSX all supported)
  - name: template_id
    type: str
    required: true
    description: Saved xlsx template id (from /api/templates)
  - name: hint
    type: str
    required: false
    description: Optional context to focus extraction
  - name: title
    type: str
    required: false
    description: Optional title override for the rendered workbook
  - name: mapping
    type: dict
    required: false
    description: "Explicit {\"template_table_name\": \"extracted_table_name\"} overrides; otherwise fuzzy-matched"
outputs:
  - name: file_path
    type: str
  - name: file_url
    type: str
  - name: title
    type: str
  - name: template_id
    type: str
  - name: source_document_count
    type: int
  - name: extracted_table_count
    type: int
  - name: mapping_report
    type: list[dict]
    description: "List of {template_table, filled_from, source_document_id, row_count, similarity} per template table"
  - name: model
    type: str
---

# populate-xlsx-from-source

This skill implements the headline OfficePlane flow: **ingest a document → fill an Excel template automatically**.

## Two-Step Composition

### Step 1 — Extract (`extract-tabular-data`)

The handler calls `extract-tabular-data` once per `source_document_id`. Each call scans the ingested document's pages using a vision model and returns a list of tables:

```json
{ "tables": [{"name": "...", "headers": [...], "rows": [[...]]}] }
```

All tables from all sources are pooled into a single candidate set.

### Step 2 — Map + Apply (`xlsx-template-apply`)

The template is loaded from disk to discover its table sections (name + expected headers). Each template table is matched against the pool of extracted tables:

1. **Explicit mapping** (`mapping` input): if the caller provides `{"Revenue": "Q3 Regional"}`, the named extracted table is used directly.
2. **Fuzzy header similarity** (Jaccard on lowercased word-token sets): the extracted table whose header set is most similar to the template table's declared headers wins, provided the score is above a threshold (`0.35`). This handles minor label differences such as "Revenue ($)" vs "Revenue".

The matched tables are assembled into a `{table_name: [[row]]}` payload and forwarded to `xlsx-template-apply`, which renders the final `.xlsx` file.

## Header Similarity

Jaccard similarity is computed on lowercased word tokens:

```
similarity = |tokens(A) ∩ tokens(B)| / |tokens(A) ∪ tokens(B)|
```

A threshold of `0.35` is used. Template tables with no match above the threshold appear in `mapping_report` with `filled_from: null` and `row_count: 0`.

## Outputs

- `file_path` / `file_url` — location of the rendered `.xlsx` file
- `mapping_report` — list of `{template_table, filled_from, source_document_id, row_count, similarity}` entries, one per template table
- `extracted_table_count` — total tables extracted across all sources
- `source_document_count` — number of source documents processed
