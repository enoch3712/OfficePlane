# OfficePlane

Enterprise-grade agentic runtime for Office artifacts (Render Plane v0.1).

## Features

- **Document Conversion**: PPTX/PPT/DOCX/XLSX → PDF
- **Image Rendering**: PDF → PNG/JPEG per page
- **Multiple Drivers**:
  - `mock` - For testing (no LibreOffice needed)
  - `libreoffice` - Python subprocess driver
  - `rust` - High-performance native driver (~50% faster)

## Quickstart

### Docker (Recommended)

```bash
docker build -t officeplane -f docker/Dockerfile .
docker run --rm -p 8001:8001 officeplane
curl -F "file=@your.pptx" "http://localhost:8001/render?dpi=120&output=both&inline=true"
```

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests (mock driver, no LibreOffice needed)
pytest -v

# Run server with mock driver
OFFICEPLANE_DRIVER=mock uvicorn officeplane.api.main:app --port 8001
```

## High-Performance Native Driver

For maximum performance, build the Rust native module:

```bash
# Prerequisites: Rust toolchain (https://rustup.rs)
./scripts/build_native.sh

# Run with native driver
OFFICEPLANE_DRIVER=rust uvicorn officeplane.api.main:app --port 8001
```

### Performance Comparison

| Driver | Convert + Render | Concurrency |
|--------|-----------------|-------------|
| `libreoffice` | ~1.1s | Good (process pool) |
| `rust` | ~0.5-0.6s | Excellent (native threads) |

## API

### POST /render

Convert and render an Office document.

**Parameters:**
- `file` (form): The document file
- `dpi` (query): Image resolution (72-300, default: 120)
- `output` (query): `pdf`, `images`, or `both` (default: `both`)
- `inline` (query): Return base64 data inline (default: `true`)
- `image_format` (query): `png` or `jpeg` (default: `png`)

**Response:**
```json
{
  "request_id": "uuid",
  "input": {"filename": "deck.pptx", "size_bytes": 12345},
  "pdf": {"sha256": "...", "base64": "..."},
  "pages": [
    {"page": 1, "dpi": 120, "width": 1280, "height": 720, "sha256": "...", "base64": "..."}
  ],
  "manifest": {
    "pages_count": 1,
    "timings_ms": {"convert": 800, "render": 200, "total": 1050},
    "versions": {"officeplane": "0.1.0", "driver": "libreoffice"}
  }
}
```

### GET /health

Health check with pool status.

### GET /metrics

Prometheus metrics endpoint.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OFFICEPLANE_DRIVER` | `libreoffice` | Driver: `mock`, `libreoffice`, `rust` |
| `POOL_SIZE` | `6` | Number of LibreOffice instances |
| `CONVERT_TIMEOUT_SEC` | `45` | Conversion timeout |
| `OUTPUT_MODE` | `inline` | Response mode: `inline` or `artifacts` |
| `DATA_DIR` | `/data` | Artifact storage directory |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI (Python)                            │
│         Routes, validation, manifest, observability             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│   Python Driver         │  │   Rust Driver           │
│   (subprocess pool)     │  │   (native, PyO3)        │
└───────────┬─────────────┘  └───────────┬─────────────┘
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LibreOffice + MuPDF                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agentic Document Editing

OfficePlane goes beyond simple document conversion. It provides an **agentic runtime** for intelligent document manipulation, powered by LLMs.

### The Plan-Execute-Verify Protocol

Traditional MCP/tool patterns are "chatty" - each action requires a round-trip:

```
Traditional Pattern (N round-trips):
┌──────────┐     ┌──────────┐
│  Client  │────▶│  Server  │  tool_call(action_1) → result_1
│  (LLM)   │◀────│  (MCP)   │  tool_call(action_2) → result_2
│          │────▶│          │  tool_call(action_3) → result_3
│          │◀────│          │  ... repeat N times
└──────────┘     └──────────┘
```

OfficePlane introduces a **Plan-Execute-Verify** pattern that batches operations:

```
OfficePlane Pattern (1 round-trip):
┌──────────┐                      ┌──────────────────────────────────┐
│  Client  │─── plan_request ───▶│         OfficePlane              │
│  (LLM)   │                      │  ┌─────────────────────────────┐ │
│          │                      │  │ 1. PLAN   - Generate actions│ │
│          │                      │  │ 2. EXECUTE - Run atomically │ │
│          │◀── verified_result ──│  │ 3. VERIFY  - Confirm intent │ │
└──────────┘                      │  └─────────────────────────────┘ │
                                  └──────────────────────────────────┘
```

### Why This Matters

| Aspect | Traditional MCP | Plan-Execute-Verify |
|--------|-----------------|---------------------|
| **Round-trips** | N (one per action) | 1 (batched) |
| **Atomicity** | None (partial failures) | All-or-nothing |
| **Verification** | Client must check | Server confirms intent |
| **Context** | Lost between calls | Full intent preserved |
| **Latency** | High (network × N) | Low (single request) |

### How It Works

#### 1. Plan Generation
Client sends a high-level intent, server returns a structured plan:

```json
// Request
POST /documents/{id}/plan
{ "prompt": "Add a new section with content Hello World" }

// Response - Executable plan with dependency placeholders
{
  "actions": [
    {
      "id": "node_0",
      "action": "add_section",
      "inputs": { "chapter_id": "existing-uuid", "title": "New Section" }
    },
    {
      "id": "node_1",
      "action": "write_page",
      "inputs": { "section_id": "$node_0.id", "content": "Hello World" }
    }
  ]
}
```

The `$node_0.id` placeholder creates dependencies between actions - the server resolves these during execution.

#### 2. Atomic Execution
Client approves the plan, server executes all actions atomically:

```json
POST /documents/{id}/execute
{ "tree": { "tree": [...actions...] } }

// Response
{
  "success": true,
  "completed": 2,
  "total": 2,
  "progress": [
    { "node_id": "node_0", "status": "completed", "output": { "id": "new-section-uuid" } },
    { "node_id": "node_1", "status": "completed", "output": { "id": "new-page-uuid" } }
  ]
}
```

#### 3. Intent Verification
Server uses AI to verify the *intent* was achieved, not just that actions ran:

```json
POST /documents/{id}/verify
{ "original_request": "Add a new section with content Hello World" }

// Response
{
  "verified": true,
  "confidence": 1.0,
  "findings": [
    { "check": "Section 'New Section' exists", "passed": true },
    { "check": "Content contains 'Hello World'", "passed": true }
  ],
  "summary": "User request was successfully fulfilled."
}
```

### MCP Server Vision

OfficePlane will expose this as an MCP server, offering tools that return **verified outcomes** rather than raw results:

```typescript
// Instead of multiple tool calls...
const section = await mcp.call("create_section", { ... });
const page = await mcp.call("create_page", { section_id: section.id, ... });
const verified = await mcp.call("check_content", { ... });

// ...one declarative call with built-in verification
const result = await mcp.call("officeplane_edit", {
  document_id: "...",
  intent: "Add a new section with content Hello World",
  verify: true
});
// result.verified === true, result.confidence === 1.0
```

### Available Actions

| Action | Description | Inputs |
|--------|-------------|--------|
| `add_chapter` | Add chapter to document | `document_id`, `title`, `order_index` |
| `add_section` | Add section to chapter | `chapter_id`, `title`, `order_index` |
| `write_page` | Write content to new page | `section_id`, `content`, `page_number` |
| `edit_page` | Modify existing page | `page_id`, `content` |
| `delete_page` | Remove a page | `page_id` |

### Placeholder Dependencies

Actions can reference outputs from previous actions using `$node_N.field` syntax:

```json
{
  "actions": [
    { "id": "node_0", "action": "add_chapter", "inputs": { "document_id": "doc-123", "title": "New Chapter" } },
    { "id": "node_1", "action": "add_section", "inputs": { "chapter_id": "$node_0.id", "title": "Section 1" } },
    { "id": "node_2", "action": "write_page", "inputs": { "section_id": "$node_1.id", "content": "Hello!" } }
  ]
}
```

The server resolves `$node_0.id` to the actual UUID returned by the first action before executing the second.

---

## License

MIT
