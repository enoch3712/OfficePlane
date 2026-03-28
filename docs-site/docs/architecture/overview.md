---
sidebar_position: 1
title: Architecture Overview
---

# Architecture Overview

OfficePlane is a multi-service system built around a 5-step document mutation pipeline. This page covers the high-level design, service topology, and how components connect.

## System Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client Layer                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │  Next.js UI  │    │  REST API    │    │  WebSocket   │              │
│  │  :3000       │    │  Clients     │    │  Clients     │              │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘              │
└─────────┼───────────────────┼───────────────────┼──────────────────────┘
          │                   │                   │
┌─────────┼───────────────────┼───────────────────┼──────────────────────┐
│         ▼                   ▼                   ▼                      │
│  ┌─────────────────────────────────────────────────────┐               │
│  │                FastAPI Application                   │               │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐      │               │
│  │  │ Management │ │ Generation │ │ Team       │      │               │
│  │  │ Routes     │ │ Routes     │ │ Routes     │      │               │
│  │  └──────┬─────┘ └──────┬─────┘ └──────┬─────┘      │               │
│  │         │               │               │            │               │
│  │  ┌──────▼───────────────▼───────────────▼──────┐    │               │
│  │  │            Task Queue (Workers)              │    │               │
│  │  └──────┬──────────────────────────────┬───────┘    │               │
│  └─────────┼──────────────────────────────┼────────────┘               │
│            │                              │                             │
│  ┌─────────▼────────┐         ┌──────────▼─────────┐                  │
│  │   PostgreSQL 16   │         │     Redis 7         │                  │
│  │   + pgvector      │         │   Task dispatch     │                  │
│  │   Source of truth │         │   Document locks    │                  │
│  │   Documents, tasks│         │   SSE pub/sub       │                  │
│  └──────────────────┘         └────────────────────┘                  │
└───────────────────────────────────────────────────────────────────────┘
```

## Core Modules

### API Layer (`src/officeplane/api/`)

The FastAPI application exposes REST endpoints and WebSocket connections. Key route groups:

- **Management** — Document CRUD, instances, tasks, upload, plan/execute/verify
- **Generation** — Async content generation with SSE streaming
- **Teams** — Multi-agent team orchestration
- **System** — Health checks, Prometheus metrics

### Document Models (`src/officeplane/documents/`)

Documents are stored as a hierarchy:

```
Document
├── Chapter
│   └── Section
│       └── Page
│           └── Chunk (text + embedding)
```

The `DocumentStore` provides an async repository pattern for all CRUD operations, exports (markdown, DOCX, PDF), and vector search.

### Ingestion Pipeline (`src/officeplane/ingestion/`)

Converts uploaded files into the document hierarchy using a 7-step vision pipeline. See [Document Ingestion](/docs/features/ingestion) for details.

### Task Queue (`src/officeplane/management/task_queue.py`)

Redis-backed queue with document-level locking. See [Task Queue](/docs/architecture/task-queue) for details.

### Planning System (`src/officeplane/components/planning/`)

Generates action trees from natural language prompts, executes them atomically with dependency resolution, and verifies results. See [Plan-Execute-Verify](/docs/features/plan-execute-verify).

### Content Agent (`src/officeplane/content_agent/`)

Async content generation using DeepAgents with OpenAI fallback. Streams events via SSE. See [Content Generation](/docs/features/content-generation).

### Agent Teams (`src/officeplane/agent_team/`)

Parallel multi-agent execution with Redis-backed task sharing. See [Agent Teams](/docs/features/agent-teams).

### Broker (`src/officeplane/broker/`)

Abstraction layer over queue backends. Production uses Redis; development can use in-memory.

### Drivers (`src/officeplane/drivers/`)

Document format conversion (DOCX/PPTX to PDF, PDF to images). Three implementations: LibreOffice (subprocess pool), Rust native (PyO3), and Mock.

## Data Flow

```
Upload ──> Ingestion ──> Document Store ──> Plan/Execute/Verify ──> Download
                              │
                              ├──> Content Generation (async)
                              ├──> Agent Teams (parallel)
                              └──> Hooks (event-driven)
```

All mutations are serialized through the task queue to guarantee atomicity and prevent concurrent edits to the same document.
