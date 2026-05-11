---
name: xlsx-template-save
description: Save a generated workbook's shape (headers, formats, charts, KPIs) as a reusable template — strips data rows
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: workspace_id
    type: str
    required: true
    description: Workspace under /data/workspaces/<id>/ containing the source document.json (a Workbook)
  - name: name
    type: str
    required: true
    description: Human-readable template name
  - name: description
    type: str
    required: false
outputs:
  - name: template_id
    type: str
  - name: name
    type: str
  - name: path
    type: str
  - name: sheet_count
    type: int
  - name: table_count
    type: int
---
