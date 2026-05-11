---
sidebar_position: 7
title: Generating Documents (Word + PowerPoint)
---

# Generating Documents (Word + PowerPoint)

OfficePlane generates `.docx` and `.pptx` files from natural language prompts via two job endpoints. Both endpoints return immediately with a job ID and stream progress over SSE.

## Generating a Word Document

```bash
POST /api/jobs/invoke/generate-docx
Content-Type: application/json

{
  "topic": "Overview of quantum-safe cryptography standards",
  "page_count": 8,
  "audience": "engineering team",
  "tone": "technical"
}
```

**Response (202 Accepted):**

```json
{
  "job_id": "job_01j2kqx8v",
  "status": "queued",
  "stream_url": "/api/jobs/job_01j2kqx8v/stream",
  "skill": "generate-docx"
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topic` | string | yes | Subject matter of the document |
| `page_count` | integer | no (default: 5) | Target page count |
| `audience` | string | no | Intended reader — influences vocabulary and depth |
| `tone` | string | no | Writing register: `technical`, `executive`, `educational` |

---

## Generating a PowerPoint Presentation

```bash
POST /api/jobs/invoke/generate-pptx
Content-Type: application/json

{
  "topic": "Q3 infrastructure cost reduction initiative",
  "slide_count": 12,
  "style": "professional",
  "audience": "executive leadership",
  "tone": "executive"
}
```

**Response (202 Accepted):**

```json
{
  "job_id": "job_01j3mnp2q",
  "status": "queued",
  "stream_url": "/api/jobs/job_01j3mnp2q/stream",
  "skill": "generate-pptx"
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topic` | string | yes | Subject matter of the presentation |
| `slide_count` | integer | no (default: 10) | Target number of slides |
| `style` | string | no | Visual register: `professional`, `minimal`, `bold` |
| `audience` | string | no | Intended audience — influences slide density |
| `tone` | string | no | Writing register: `technical`, `executive`, `educational` |

---

## The Document JSON Schema the Model Emits

The LLM is prompted to emit a document tree conforming to `schema_version 1.0` (see [The Document Tree](/architecture/document-tree)) before the renderer converts it to OOXML. The intermediate JSON is stored alongside the output file and forms the basis for subsequent edits.

A minimal generation output looks like:

```json
{
  "schema_version": "1.0",
  "id": "doc_01j2kqx8v",
  "title": "Quantum-Safe Cryptography Standards",
  "sections": [
    {
      "id": "sec_01",
      "title": "Introduction",
      "depth": 0,
      "children": [],
      "blocks": [
        { "id": "blk_01", "type": "heading", "level": 1, "content": "Introduction" },
        { "id": "blk_02", "type": "paragraph", "content": "Post-quantum cryptography addresses..." }
      ]
    }
  ]
}
```

The renderer iterates sections depth-first, maps each `Block` to the corresponding OOXML element, and writes the file. Because the intermediate JSON is persisted, every generation is immediately editable without re-ingestion.

---

## Example Results

The following results are from smoke tests run against the default `flash`-tier model:

| Prompt | Format | Slides / Pages | Generation Time | File Size |
|--------|--------|----------------|-----------------|-----------|
| "Overview of quantum-safe cryptography, 8 pages, technical" | DOCX | 8 pp | 18 s | 42 KB |
| "Q3 infra cost reduction, 12 slides, executive" | PPTX | 12 slides | 24 s | 98 KB |
| "Onboarding guide for new engineers, 6 pages" | DOCX | 6 pp | 14 s | 31 KB |
| "Product roadmap pitch deck, 15 slides" | PPTX | 15 slides | 31 s | 124 KB |

Times measured end-to-end from job submission to file available, on a single worker with DeepSeek v4-flash.

---

## Workspace Layout

Each generation job creates an isolated workspace directory:

```
/data/workspaces/<job_id>/
├── document.json        # Intermediate document tree (schema_version 1.0)
├── output.docx          # or output.pptx
└── revisions/
    └── rev_00.json      # Initial revision snapshot (parent_revision_id: null)
```

Future versions will write incremental `rev_N.json` snapshots for each agent edit applied to the workspace before final render.

The workspace is retained for 24 hours after job completion, then pruned by the cleanup worker. Download the output file before it expires:

```bash
GET /api/jobs/{job_id}/output
```

Returns the binary file with the appropriate `Content-Type` header (`application/vnd.openxmlformats-officedocument.wordprocessingml.document` or `.presentationml.presentation`).

---

## Streaming Progress

Connect to the SSE stream to observe generation in real time:

```bash
GET /api/jobs/{job_id}/stream
```

```
event: start
data: {"job_id": "job_01j2kqx8v", "skill": "generate-docx"}

event: delta
data: {"text": "Drafting section: Introduction"}

event: delta
data: {"text": "Drafting section: Background and Standards"}

event: tool_call
data: {"tool": "write_file", "path": "document.json"}

event: stop
data: {"job_id": "job_01j2kqx8v", "document_id": "doc_01j2kqx8v", "duration_ms": 18340}
```
