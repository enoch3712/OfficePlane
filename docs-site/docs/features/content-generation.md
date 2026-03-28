---
sidebar_position: 3
title: Content Generation
---

# Content Generation

OfficePlane can generate documents from scratch — presentations, reports, and more — using an async agent workflow that streams progress in real time.

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  POST        │────>│  Task Queue  │────>│  Agent       │────>│  Document    │
│  /api/generate│     │  (Redis)     │     │  Runner      │     │  Store       │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                                         │
       │         SSE Stream                      │
       │◄────────────────────────────────────────┘
       │    event: start
       │    event: delta (progress text)
       │    event: tool_call
       │    event: tool_result
       │    event: stop (document_id)
```

1. **Submit** — `POST /api/generate` returns immediately with a job ID and stream URL (HTTP 202)
2. **Queue** — The job is enqueued in Redis as a task
3. **Execute** — A worker picks it up and runs the `ContentAgentRunner`
4. **Stream** — Events are published to Redis pub/sub and delivered as SSE
5. **Store** — The generated content is saved to the document store

## API

### Start Generation

```bash
POST /api/generate
{
  "prompt": "Create a 10-slide pitch deck about AI-powered document automation",
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

### Stream Progress

```bash
GET /api/generate/{job_id}/stream
```

Returns an SSE stream:

```
event: start
data: {"job_id": "gen-abc-123", "timestamp": "..."}

event: delta
data: {"text": "Creating slide 1: Title slide with company name..."}

event: tool_call
data: {"tool": "pptxgenjs", "args": {"slide": 1, "title": "AI Doc Automation"}}

event: tool_result
data: {"output": "Slide 1 created successfully"}

event: delta
data: {"text": "Creating slide 2: Problem statement..."}

... (more events) ...

event: stop
data: {"job_id": "gen-abc-123", "document_id": "doc-xyz", "duration_ms": 45000}
```

### Check Status

```bash
GET /api/generate/{job_id}
```

```json
{
  "job_id": "gen-abc-123",
  "status": "completed",
  "document_id": "doc-xyz",
  "duration_ms": 45000
}
```

### Cancel

```bash
DELETE /api/generate/{job_id}
```

## Content Agent Internals

The `ContentAgentRunner` uses a two-tier approach:

### Primary: DeepAgents

When available, the runner uses DeepAgents with a `LocalShellBackend`:

1. Creates a temporary workspace directory
2. Initializes the agent with tool access (bash, file I/O, Python, Node.js)
3. The agent autonomously decides how to build the document
4. Progress is streamed via SSE in real time
5. Workspace is cleaned up after completion

### Fallback: Direct OpenAI

If DeepAgents is unavailable, falls back to OpenAI directly:

1. Generates a `pptxgenjs` script via GPT-4o
2. Executes the script in the workspace
3. Saves the resulting file

## Supported Formats

| Format | Tool Used | Notes |
|--------|-----------|-------|
| PPTX | pptxgenjs, python-pptx | Presentations |
| HTML | Direct generation | Reports, web content |
| Markdown | Direct generation | Documentation |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTENT_AGENT_MODEL` | `gpt-4o` | LLM model for generation |
| `CONTENT_AGENT_TIMEOUT` | `600` | Timeout in seconds |
| `CONTENT_AGENT_WORKSPACE` | `/data/workspaces` | Temp directory |
