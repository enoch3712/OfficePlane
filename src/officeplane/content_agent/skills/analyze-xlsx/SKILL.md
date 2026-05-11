---
name: analyze-xlsx
description: Analyze an ingested .xlsx document for formula errors, suspected typos, outliers, missing totals, and dead references
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: document_id
    type: str
    required: true
    description: Prisma Document.id of an .xlsx that was ingested via Phase 33
  - name: max_issues
    type: int
    required: false
    description: Soft cap on number of issues returned (default 20)
outputs:
  - name: document_id
    type: str
  - name: title
    type: str
  - name: sheet_count
    type: int
  - name: issue_count
    type: int
  - name: issues
    type: list[dict]
    description: "[{severity, category, sheet, cell, description, suggestion}]"
  - name: model
    type: str
---

# analyze-xlsx

Audits a Phase-33-ingested Excel workbook for data quality problems. The skill
walks every page (one page = one worksheet) of the ingested document, collects
the Markdown/text representation produced during ingestion, and asks DeepSeek to
identify problems across six categories.

## How it works

1. Fetches the document record from the database using `document_id`.
2. Verifies the document was ingested as an Excel file (`sourceFormat` is `xlsx`
   or `xls`). Rejects other formats with a 400 error.
3. Walks the chapter → section → page hierarchy produced by the Phase-33
   ingestion pipeline (falls back to a flat page list for older shapes).
4. Caps each page's text at 4 000 characters to stay within model context limits,
   then assembles all sheets into one prompt blob separated by `--- next sheet ---`.
5. Sends the assembled prompt to DeepSeek (model configured via
   `OFFICEPLANE_AGENT_MODEL_FLASH`, default `deepseek/deepseek-v4-flash`) with
   `temperature=0` and `response_format={"type": "json_object"}` for
   deterministic, machine-readable output.
6. Normalises and validates every issue returned by the model:
   - Unknown severity values are coerced to `"low"`.
   - Issues with an unrecognised category are silently dropped.
   - The list is hard-capped at `max_issues` (default 20, max 100).
7. Writes a `SkillInvocation` audit row via `persist_skill_invocation`.

## Issue categories

| Category | What it flags |
|---|---|
| `formula_error` | Formula returns `#REF!`, `#DIV/0!`, `#VALUE!`, or similar Excel errors |
| `suspected_typo` | A number that looks off-by-magnitude relative to its column peers |
| `outlier` | A value dramatically larger or smaller than its neighbours |
| `missing_total` | A column of numeric values with no totals row when one is expected |
| `dead_reference` | A formula references a cell or sheet name that does not exist |
| `inconsistent_format` | Mixed text/numbers in a column, or inconsistent units (%, decimal, $) |

## Severity levels

- `high` — likely causes incorrect calculations or broken reports
- `medium` — suspicious but may be intentional; warrants review
- `low` — cosmetic or style issue

## Output shape

```json
{
  "document_id": "cuid...",
  "title": "Q3 Budget Review",
  "sheet_count": 4,
  "issue_count": 3,
  "issues": [
    {
      "severity": "high",
      "category": "formula_error",
      "sheet": "Summary",
      "cell": "D12",
      "description": "=SUM(B2:B11) returns #REF! — referenced range is outside the sheet",
      "suggestion": "Check that the source range B2:B11 exists and extend it if needed"
    }
  ],
  "model": "deepseek/deepseek-v4-flash"
}
```

If no issues are found the `issues` list is empty and `issue_count` is `0`.
If the workbook has no page content (empty ingestion), the skill returns early
with `sheet_count=0` and a `note` field explaining the situation.
