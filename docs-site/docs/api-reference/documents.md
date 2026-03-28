---
sidebar_position: 2
title: Documents
---

# Documents API

Manage documents — upload, read, edit, download, and explore the document hierarchy.

## Upload a Document

Ingest a DOCX or PDF file. Triggers the full [ingestion pipeline](/docs/features/ingestion).

```bash
POST /api/documents/upload
Content-Type: multipart/form-data
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | file | The document file (DOCX, PDF) |

**Example:**

```bash
curl -X POST http://localhost:8001/api/documents/upload \
  -F "file=@quarterly-report.docx"
```

**Response (200):**

```json
{
  "id": "doc-abc-123",
  "title": "Quarterly Report Q4 2025",
  "author": "Finance Team",
  "source_format": "docx",
  "chapters": [
    {
      "id": "ch-001",
      "title": "Executive Summary",
      "order_index": 0,
      "sections": [ ... ]
    }
  ],
  "created_at": "2026-03-18T10:30:00Z"
}
```

## List Documents

```bash
GET /api/documents
```

**Response:**

```json
[
  {
    "id": "doc-abc-123",
    "title": "Quarterly Report Q4 2025",
    "source_format": "docx",
    "created_at": "2026-03-18T10:30:00Z"
  }
]
```

## Get Document

Retrieve a document with its full hierarchy (chapters, sections, pages).

```bash
GET /api/documents/{id}
```

**Response:**

```json
{
  "id": "doc-abc-123",
  "title": "Quarterly Report Q4 2025",
  "chapters": [
    {
      "title": "Executive Summary",
      "sections": [
        {
          "title": "Key Metrics",
          "pages": [
            {
              "page_number": 1,
              "content": "Revenue grew 23% year-over-year...",
              "word_count": 342
            }
          ]
        }
      ]
    }
  ]
}
```

## Get Document Outline

Lightweight table-of-contents view without page content.

```bash
GET /api/documents/{id}/outline
```

## Download Document

Export the document in various formats.

```bash
GET /api/documents/{id}/download?format={format}
```

| Format | Description |
|--------|-------------|
| `original` | Original uploaded file bytes |
| `docx` | Regenerated DOCX |
| `markdown` | Markdown export |
| `pdf` | PDF via LibreOffice |

## Delete Document

```bash
DELETE /api/documents/{id}
```

## Plan Changes

Generate an action tree from a natural language prompt.

```bash
POST /api/documents/{id}/plan
Content-Type: application/json
```

```json
{
  "prompt": "Add a chapter about risk mitigation strategies"
}
```

**Response:**

```json
{
  "actions": [
    {
      "node_id": "node_0",
      "action": "add_chapter",
      "params": { "title": "Risk Mitigation Strategies", "order_index": 4 },
      "depends_on": []
    },
    {
      "node_id": "node_1",
      "action": "add_section",
      "params": { "title": "Identified Risks", "chapter_id": "$node_0.id" },
      "depends_on": ["node_0"]
    }
  ]
}
```

## Execute Plan

Run an action tree atomically.

```bash
POST /api/documents/{id}/execute
Content-Type: application/json
```

```json
{
  "actions": [ ... ]
}
```

## Verify Changes

Check if executed changes match the original intent.

```bash
POST /api/documents/{id}/verify
Content-Type: application/json
```

```json
{
  "original_request": "Add a chapter about risk mitigation strategies"
}
```

**Response:**

```json
{
  "verified": true,
  "confidence": 0.92,
  "report": "Document now contains a Risk Mitigation Strategies chapter with appropriate sections."
}
```
