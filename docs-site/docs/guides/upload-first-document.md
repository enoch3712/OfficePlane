---
sidebar_position: 1
title: Upload Your First Document
---

# Upload Your First Document

This guide walks you through uploading a document, exploring its extracted structure, and making your first AI-powered edit.

## Prerequisites

- OfficePlane running via `docker compose up -d` (see [Quick Start](/docs/getting-started/quickstart))
- A DOCX or PDF file to upload

## Step 1: Upload via the UI

1. Open **http://localhost:3000** in your browser
2. Navigate to the **Documents** page from the sidebar
3. Click the **Upload** button in the top-right corner
4. Drag and drop your file or click to browse
5. Wait for ingestion to complete (you'll see a progress indicator)

The ingestion pipeline runs automatically:
- Format detection
- PDF conversion (if DOCX)
- Page rendering to images
- Gemini vision analysis
- Structure parsing
- Storage with embeddings

## Step 2: Upload via the API

Alternatively, use `curl`:

```bash
curl -X POST http://localhost:8001/api/documents/upload \
  -F "file=@my-report.docx"
```

The response includes the full document hierarchy:

```json
{
  "id": "doc-abc-123",
  "title": "Q4 2025 Report",
  "chapters": [
    {
      "title": "Executive Summary",
      "sections": [
        {
          "title": "Key Highlights",
          "pages": [
            { "page_number": 1, "content": "...", "word_count": 285 }
          ]
        }
      ]
    },
    {
      "title": "Financial Overview",
      "sections": [ ... ]
    }
  ]
}
```

## Step 3: Explore the Structure

### In the UI

The Documents page shows a tree sidebar on the left with the full hierarchy:

```
Q4 2025 Report
├── Executive Summary
│   ├── Key Highlights
│   └── Performance Metrics
├── Financial Overview
│   ├── Revenue Breakdown
│   └── Expense Analysis
└── Outlook
    └── Next Quarter Goals
```

Click any section to view its content in the center panel.

### Via the API

```bash
# Full document with content
curl http://localhost:8001/api/documents/doc-abc-123

# Lightweight outline (no page content)
curl http://localhost:8001/api/documents/doc-abc-123/outline
```

## Step 4: Plan Your First Edit

Use the planning chat in the UI, or call the API directly:

```bash
curl -X POST http://localhost:8001/api/documents/doc-abc-123/plan \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Add a Risk Analysis section to the Financial Overview chapter"}'
```

The planner returns an action tree — a set of operations it will perform:

```json
{
  "actions": [
    { "action": "add_section", "params": { "title": "Risk Analysis", "chapter_id": "ch-002" } },
    { "action": "write_page", "params": { "content": "...", "section_id": "$node_0.id" } }
  ]
}
```

## Step 5: Execute the Plan

```bash
curl -X POST http://localhost:8001/api/documents/doc-abc-123/execute \
  -H "Content-Type: application/json" \
  -d '{"actions": [...]}'
```

The executor runs every action atomically. If anything fails, all changes roll back.

## Step 6: Verify

```bash
curl -X POST http://localhost:8001/api/documents/doc-abc-123/verify \
  -H "Content-Type: application/json" \
  -d '{"original_request": "Add a Risk Analysis section to the Financial Overview chapter"}'
```

The verifier confirms:

```json
{
  "verified": true,
  "confidence": 0.94,
  "report": "A Risk Analysis section has been added to the Financial Overview chapter with appropriate content."
}
```

## Step 7: Download

```bash
# Original format
curl -O http://localhost:8001/api/documents/doc-abc-123/download?format=original

# As markdown
curl http://localhost:8001/api/documents/doc-abc-123/download?format=markdown

# As PDF
curl -O http://localhost:8001/api/documents/doc-abc-123/download?format=pdf
```
