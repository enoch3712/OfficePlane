---
sidebar_position: 5
title: Generation
---

# Generation API

Async content generation with real-time SSE streaming.

## Start Generation

```bash
POST /api/generate
Content-Type: application/json
```

```json
{
  "prompt": "Create a 10-slide investor pitch deck for a B2B SaaS company",
  "output_format": "pptx",
  "model": "gpt-4o",
  "options": {
    "num_slides": 10,
    "style": "professional"
  }
}
```

**Response (202 Accepted):**

```json
{
  "job_id": "gen-abc-123",
  "status": "queued",
  "stream_url": "/api/generate/gen-abc-123/stream"
}
```

## Stream Progress (SSE)

```bash
GET /api/generate/{job_id}/stream
Accept: text/event-stream
```

**Events:**

```
event: start
data: {"job_id": "gen-abc-123", "timestamp": "2026-03-18T10:30:00Z"}

event: delta
data: {"text": "Analyzing prompt and planning slide structure..."}

event: tool_call
data: {"tool": "pptxgenjs", "args": {"action": "addSlide", "title": "Problem Statement"}}

event: tool_result
data: {"output": "Slide 2 created: Problem Statement"}

event: stop
data: {"job_id": "gen-abc-123", "document_id": "doc-xyz", "duration_ms": 45200}
```

## Get Job Status

```bash
GET /api/generate/{job_id}
```

```json
{
  "job_id": "gen-abc-123",
  "status": "completed",
  "document_id": "doc-xyz",
  "output_format": "pptx",
  "duration_ms": 45200,
  "created_at": "2026-03-18T10:30:00Z",
  "completed_at": "2026-03-18T10:30:45Z"
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `queued` | Waiting in task queue |
| `running` | Agent is executing |
| `completed` | Finished, document available |
| `failed` | Generation failed |
| `cancelled` | Cancelled by user |

## Cancel Job

```bash
DELETE /api/generate/{job_id}
```

## Output Formats

| Format | Description |
|--------|-------------|
| `pptx` | PowerPoint presentation |
| `html` | HTML document |
| `markdown` | Markdown document |
