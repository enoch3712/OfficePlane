---
sidebar_position: 2
title: Generate a Presentation
---

# Generate a Presentation

This guide shows you how to generate a PowerPoint presentation from scratch using OfficePlane's content generation agent.

## Prerequisites

- OfficePlane running (`docker compose up -d`)
- An OpenAI API key set in your `.env` (`OPENAI_API_KEY=sk-...`)

## Using the UI

1. Open **http://localhost:3000**
2. Navigate to **Generate** from the sidebar
3. Enter your prompt in the text area:

```
Create a 10-slide investor pitch deck for an AI-powered document
automation platform. Include: title slide, problem statement,
solution overview, market size, product demo, business model,
traction metrics, team, competitive landscape, and ask/next steps.
```

4. Select **PPTX** as the output format
5. Click **Generate**

The right panel shows real-time SSE events as the agent works:

```
▶ Agent started
  Creating slide structure...
  Slide 1: Title — "AI Document Automation"
  Slide 2: Problem — "Manual document workflows cost enterprises..."
  ...
  Slide 10: Next Steps — "Join our seed round"
✓ Generation complete (42s)
```

6. Click **Download** to get the PPTX file

## Using the API

### Start the job

```bash
curl -X POST http://localhost:8001/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a 10-slide investor pitch deck for an AI-powered document automation platform",
    "output_format": "pptx",
    "model": "gpt-4o",
    "options": {
      "num_slides": 10,
      "style": "professional"
    }
  }'
```

**Response:**

```json
{
  "job_id": "gen-abc-123",
  "status": "queued",
  "stream_url": "/api/generate/gen-abc-123/stream"
}
```

### Stream progress

```bash
curl -N http://localhost:8001/api/generate/gen-abc-123/stream
```

You'll see SSE events:

```
event: start
data: {"job_id": "gen-abc-123"}

event: delta
data: {"text": "Planning slide structure: 10 slides..."}

event: tool_call
data: {"tool": "pptxgenjs", "args": {"action": "createPresentation"}}

event: tool_result
data: {"output": "Presentation initialized"}

event: delta
data: {"text": "Creating Slide 1: Title slide..."}

... more events ...

event: stop
data: {"job_id": "gen-abc-123", "document_id": "doc-xyz-456", "duration_ms": 42300}
```

### Check status

```bash
curl http://localhost:8001/api/generate/gen-abc-123
```

### Download the result

Once complete, download via the document ID returned in the `stop` event:

```bash
curl -O http://localhost:8001/api/documents/doc-xyz-456/download?format=original
```

## Supported Formats

| Format | Output | Best For |
|--------|--------|----------|
| `pptx` | PowerPoint file | Presentations, pitch decks |
| `html` | HTML document | Reports, web-ready content |
| `markdown` | Markdown file | Documentation, READMEs |

## Tips

- **Be specific** in your prompt — mention slide count, topics, and style
- **Use context** — reference existing documents by uploading them first
- The agent uses **pptxgenjs** for PowerPoint creation, producing professional layouts
- Generation typically takes 30-60 seconds for a 10-slide deck
- You can **cancel** at any time: `DELETE /api/generate/{job_id}`
