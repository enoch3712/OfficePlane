---
name: generate-xlsx
description: Generate an Excel workbook (.xlsx) from ingested source documents — tabular with charts, formulas, KPI cells
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: source_document_ids
    type: list[str]
    required: true
  - name: brief
    type: str
    required: true
  - name: style
    type: str
    required: false
    description: financial / operational / executive / academic
  - name: audience
    type: str
    required: false
  - name: max_sheets
    type: int
    required: false
    description: Soft cap (default 5)
outputs:
  - name: file_path
    type: str
  - name: file_url
    type: str
  - name: title
    type: str
  - name: sheet_count
    type: int
  - name: table_count
    type: int
  - name: chart_count
    type: int
  - name: model
    type: str
  - name: source_document_ids
    type: list[str]
---

# generate-xlsx

Produces a real `.xlsx` file from ingested source documents using the Workbook
JSON schema. Always grounded — the LLM must not invent numbers; only use values
present in the sources. Supports native Excel tables, charts (bar/line/pie/scatter),
formulas (=SUM, =AVERAGE...), KPI cells, and typed columns (currency, percent, date).
