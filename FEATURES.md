# OfficePlane — Feature Document

> Agentic runtime for Office artifacts. This document catalogs all current, in-progress, and planned features to guide development.

---

## Core Platform

### F-001: Document Conversion Engine
**Status:** Shipped
**Description:** HTTP service that converts Office documents (PPTX, PPT, DOCX, XLSX) to canonical PDF format.
**Endpoint:** `POST /render`
**Key details:**
- Accepts file upload with configurable DPI (72–300), output format (pdf/images/both), image format (png/jpeg)
- Returns manifest with checksums, timings, driver version
- Supports inline (base64) and artifact (file URL) response modes

### F-002: Multi-Driver Architecture
**Status:** Shipped
**Drivers:**
| Driver | Description | Performance |
|--------|-------------|-------------|
| `mock` | No external deps, for testing/CI | Instant |
| `libreoffice` | Python subprocess pool (unoserver) | ~1.1s |
| `rust` | Native PyO3 module (LibreOffice + MuPDF) | ~0.5–0.6s |

**Config:** `OFFICEPLANE_DRIVER` env var. Pool size and timeout configurable.

### F-003: Per-Page Image Rendering
**Status:** Shipped
**Description:** Renders each PDF page to PNG or JPEG at configurable DPI. Uses PyMuPDF for rendering and Pillow for compression/optimization.

### F-004: Enterprise Observability
**Status:** Shipped
- `GET /health` — Pool status, driver readiness
- `GET /metrics` — Prometheus-format metrics (latency, failures, restarts)
- Structured audit logs with `request_id` correlation
- No auth/DB required to run end-to-end

---

## Document Ingestion Pipeline

### F-010: Format Detection
**Status:** Shipped
**Description:** Automatic format detection via magic bytes for DOCX, PDF, XLSX, PPTX.
**File:** `src/officeplane/ingestion/format_detector.py`

### F-011: Vision-Based Document Analysis
**Status:** Shipped
**Description:** Converts documents to images, then uses Gemini vision API to extract structured content (chapters, sections, pages) with semantic understanding.
**Pipeline:** Format detect → PDF convert → Page render → Image compress → Vision analyze → Structure parse → Store
**Config:**
- `OFFICEPLANE_INGESTION_VISION_PROVIDER` — `gemini` or `mock`
- `OFFICEPLANE_INGESTION_VISION_MODEL` — default `gemini-3-flash-preview`
- `OFFICEPLANE_INGESTION_BATCH_SIZE` — pages per vision call (default 8)
- `OFFICEPLANE_INGESTION_IMAGE_SIZE_KB` — target image size (default 75)

### F-012: Hierarchical Document Storage
**Status:** Shipped
**Description:** Documents stored as a hierarchy: Document → Chapter → Section → Page. Each level has metadata (title, order, word count). Backed by PostgreSQL via Prisma ORM.

### F-013: Vector Embeddings (RAG)
**Status:** Shipped
**Description:** Document chunks stored with pgvector embeddings for retrieval-augmented generation. Supports semantic search across ingested documents.
**Model:** `Chunk` with `embedding` field (pgvector)

---

## Agentic Document Editing

### F-020: Plan-Execute-Verify Protocol
**Status:** Shipped
**Description:** Replaces chatty N-round-trip MCP pattern with a single-request workflow:
1. **Plan** — Client sends intent, server generates structured action plan with dependency placeholders (`$node_0.id`)
2. **Execute** — Server runs all actions atomically (all-or-nothing)
3. **Verify** — AI confirms the intent was achieved, not just that actions ran

**Endpoints:**
- `POST /documents/{id}/plan` — Generate plan from prompt
- `POST /documents/{id}/execute` — Execute plan atomically
- `POST /documents/{id}/verify` — Verify intent fulfillment

### F-021: Action System
**Status:** Shipped
**Available actions:**
| Action | Description | Inputs |
|--------|-------------|--------|
| `add_chapter` | Add chapter to document | `document_id`, `title`, `order_index` |
| `add_section` | Add section to chapter | `chapter_id`, `title`, `order_index` |
| `write_page` | Create page with content | `section_id`, `content`, `page_number` |
| `edit_page` | Modify existing page | `page_id`, `content` |
| `delete_page` | Remove a page | `page_id` |

**Dependency resolution:** `$node_N.field` placeholders auto-resolve during execution.

### F-022: Document Editor (doctools)
**Status:** Shipped
**Description:** Context-manager-based editor for Word documents with batch operations, full transaction support (rollback on failure), and structured Result[T] error types.
**Capabilities:** StructureReader, ContentModifier, TableBuilder, PlanExecutor
**File:** `src/officeplane/doctools/`

### F-023: Spreadsheet Editor (sheettools)
**Status:** Shipped
**Description:** Excel spreadsheet editing with plan-execute-rollback pattern. Supports cell references (A1, B2), sheet operations, and atomic execution.
**Capabilities:** SheetReader, CellModifier, TableBuilder, SpreadsheetPlan
**File:** `src/officeplane/sheettools/`

---

## Orchestration & Management

### F-030: Workchestrator
**Status:** Shipped
**Description:** Sophisticated plan/delegate/review/takeover state machine for agentic document editing:
- Worker generates plan → if confidence < threshold, orchestrator takes over
- Complexity scoring for automatic escalation
- Progressive feedback on retries
- Configurable worker/orchestrator LLM providers

**Config:** `OFFICEPLANE_SETTINGS_PATH` → persisted JSON with thresholds
**File:** `src/officeplane/agentic/workchestrator.py`

### F-031: Instance Lifecycle Management
**Status:** Shipped
**Description:** Document instance state machine with heartbeat monitoring.
**States:** OPENING → OPEN → IDLE → IN_USE → CLOSING → CLOSED → ERROR → CRASHED
**Features:**
- Heartbeat every 5 seconds
- Process PID tracking
- Memory/CPU monitoring per instance
- WebSocket event broadcasting on state changes

### F-032: Task Queue
**Status:** Shipped
**Description:** Temporal-style task orchestration with priority, retry, and parent-child relationships.
**Priority levels:** LOW, NORMAL, HIGH, CRITICAL
**Task states:** QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED / RETRYING / TIMEOUT
**Features:**
- Automatic retries with exponential backoff
- `maxRetries` per task
- Parent-child task relationships
- Full execution history audit trail

### F-033: Orchestration Settings
**Status:** Shipped
**Description:** Runtime-configurable orchestration parameters persisted to JSON.
**Settings:**
- Worker/Orchestrator provider and model selection
- `worker_confidence_threshold` (default 0.68)
- `complexity_takeover_threshold` (default 0.72)
- `max_worker_retries` (default 1)
- `max_validation_issues` (default 1)

---

## User Interface

### F-040: Management Dashboard
**Status:** Shipped
**Description:** Next.js 15 dashboard at `localhost:3000` with real-time updates.
**Panels:**
- Metrics — active instances, tasks, CPU/memory
- Instances — document instance list with state badges
- Task Queue — task list with status and priority
- History — execution history timeline

### F-041: Orchestration Settings UI
**Status:** Shipped
**Route:** `/settings`
**Description:** Visual configuration panel for all workchestrator settings (thresholds, providers, models, takeover policies).

### F-042: File Upload
**Status:** Shipped
**Description:** Drag-and-drop file upload dialog with file preview and format validation.

### F-043: WebSocket Real-Time Updates
**Status:** Shipped
**Description:** Auto-reconnecting WebSocket connection for live instance/task state updates. Connection status indicator in UI.

### F-044: Chat Interface
**Status:** Shipped
**Routes:** `/chat`
**Description:** Chat-based interface for plan generation (PlanningChat) and agentic document editing (AgenticChat).

---

## Planned Features

### F-100: Async Job Endpoint
**Status:** Planned
**Description:** `POST /render_async` returns a `job_id` for long-running conversions. Clients poll or subscribe via WebSocket for completion.
**Why:** Current synchronous render blocks the connection for large documents.

### F-101: Layout Map Extraction
**Status:** Planned
**Description:** Extract text blocks with bounding boxes from rendered pages. Enables agents to reference specific regions of a document ("the table in the top-right corner").
**Why:** Critical for agent grounding — agents need spatial awareness of document layout.

### F-102: Semantic Patching for Excel
**Status:** Planned
**Description:** Table-aware patching with `WHERE`/column semantics, proofs, and validations. Goes beyond cell-level operations to support declarative data transformations.
**Why:** Current sheettools operate at cell level; semantic patching enables higher-level intent like "update all rows where Region = 'West'."

### F-103: Driver Adapters (MS Graph, Google Sheets)
**Status:** Planned
**Description:** Implement the `OfficeDriver` interface for cloud document providers (Microsoft 365 via Graph API, Google Workspace via Sheets/Docs/Slides API).
**Why:** Extends OfficePlane from local-file-only to cloud-native document editing.

### F-104: MCP Server
**Status:** Planned
**Description:** Expose Plan-Execute-Verify as an MCP server. Single `officeplane_edit` tool call with built-in verification replaces multi-step tool sequences.
**Why:** Native integration with Claude, Cursor, and other MCP-compatible clients.

### F-105: PowerPoint Editor (slidetools)
**Status:** Not started
**Description:** Plan-execute-rollback pattern for PowerPoint presentations, parallel to doctools and sheettools. Slide-level operations: add/remove/reorder slides, edit text boxes, modify layouts.
**Why:** Completes the Office trifecta (Word, Excel, PowerPoint).

### F-106: Multi-Document Operations
**Status:** Not started
**Description:** Operations that span multiple documents — e.g., "copy the summary table from the Q4 report into the board deck." Requires cross-document planning and dependency resolution.
**Why:** Real enterprise workflows frequently reference and combine multiple documents.

### F-107: Diff & Rollback UI
**Status:** Not started
**Description:** Visual diff of document changes before/after plan execution. One-click rollback to previous state. Version history timeline.
**Why:** Enterprise users need visibility and control over automated changes.

### F-108: Authentication & Multi-Tenancy
**Status:** Not started
**Description:** Optional pluggable auth (JWT, OAuth, API keys) and tenant isolation. Currently runs without auth by design.
**Why:** Required for production multi-user deployments. Auth hooks are designed-in but not yet implemented.

### F-109: Agent Workflow Harness
**Status:** Not started
**Description:** End-to-end agent workflow runner that chains: open document → analyze → plan → execute → verify → close. Supports long-running tasks (4+ hours) with checkpointing.
**Why:** The north star — replace a human who uses Office apps for multi-hour tasks.

---

## Feature Index

| ID | Feature | Status | Category |
|----|---------|--------|----------|
| F-001 | Document Conversion Engine | Shipped | Core |
| F-002 | Multi-Driver Architecture | Shipped | Core |
| F-003 | Per-Page Image Rendering | Shipped | Core |
| F-004 | Enterprise Observability | Shipped | Core |
| F-010 | Format Detection | Shipped | Ingestion |
| F-011 | Vision-Based Document Analysis | Shipped | Ingestion |
| F-012 | Hierarchical Document Storage | Shipped | Ingestion |
| F-013 | Vector Embeddings (RAG) | Shipped | Ingestion |
| F-020 | Plan-Execute-Verify Protocol | Shipped | Agentic |
| F-021 | Action System | Shipped | Agentic |
| F-022 | Document Editor (doctools) | Shipped | Agentic |
| F-023 | Spreadsheet Editor (sheettools) | Shipped | Agentic |
| F-030 | Workchestrator | Shipped | Orchestration |
| F-031 | Instance Lifecycle Management | Shipped | Orchestration |
| F-032 | Task Queue | Shipped | Orchestration |
| F-033 | Orchestration Settings | Shipped | Orchestration |
| F-040 | Management Dashboard | Shipped | UI |
| F-041 | Orchestration Settings UI | Shipped | UI |
| F-042 | File Upload | Shipped | UI |
| F-043 | WebSocket Real-Time Updates | Shipped | UI |
| F-044 | Chat Interface | Shipped | UI |
| F-100 | Async Job Endpoint | Planned | Core |
| F-101 | Layout Map Extraction | Planned | Agentic |
| F-102 | Semantic Patching for Excel | Planned | Agentic |
| F-103 | Driver Adapters (MS Graph, Google) | Planned | Core |
| F-104 | MCP Server | Planned | Agentic |
| F-105 | PowerPoint Editor (slidetools) | Not started | Agentic |
| F-106 | Multi-Document Operations | Not started | Agentic |
| F-107 | Diff & Rollback UI | Not started | UI |
| F-108 | Authentication & Multi-Tenancy | Not started | Core |
| F-109 | Agent Workflow Harness | Not started | Agentic |
