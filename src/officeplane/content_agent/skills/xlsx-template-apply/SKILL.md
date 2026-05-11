---
name: xlsx-template-apply
description: Apply a saved xlsx template with new data — fills each table by name, renders .xlsx
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: template_id
    type: str
    required: true
  - name: tables
    type: dict
    required: true
    description: Mapping table_name → list of row arrays. Each row must match the template's column count.
  - name: title
    type: str
    required: false
    description: Optional title override for the rendered workbook
outputs:
  - name: file_path
    type: str
  - name: file_url
    type: str
  - name: title
    type: str
  - name: template_id
    type: str
  - name: sheet_count
    type: int
  - name: table_count
    type: int
---
