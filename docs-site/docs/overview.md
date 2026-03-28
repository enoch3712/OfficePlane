---
sidebar_position: 1
slug: /overview
title: Overview
---

# OfficePlane

OfficePlane is an open-source **agentic runtime** for document manipulation. It provides a complete pipeline to ingest, understand, plan changes, execute edits, and verify results across office document formats — all powered by AI agents.

## What OfficePlane Does

| Capability | Description |
|-----------|-------------|
| **Document Ingestion** | Upload DOCX/PDF files. Gemini vision extracts a hierarchical structure (chapters, sections, pages) with pgvector embeddings for semantic search. |
| **Plan-Execute-Verify** | Describe what you want changed. An AI generates an action tree, executes it atomically, then verifies the result matches your intent. |
| **Content Generation** | Generate presentations, reports, and documents from scratch via async agent workflows streamed over SSE. |
| **Task Queue** | Redis-backed queue with document-level locking, instant BRPOP dispatch, retry with backoff, and parallel execution across documents. |
| **Agent Teams** | Decompose complex tasks across multiple parallel agents with shared task lists, dependency tracking, and pub/sub messaging. |
| **Document Hooks** | Attach automated checks to document lifecycle events — compliance reviews, style enforcement, cross-doc sync — triggered on every edit. |
| **Real-Time Updates** | WebSocket and SSE streaming for live progress on all operations. |

## Architecture at a Glance

Every file mutation follows a 5-step pipeline:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 1. Open      │───>│ 2. Queue     │───>│ 3. Change    │───>│ 4. Pretty    │───>│ 5. Get       │
│    Instance  │    │    (atomic)  │    │    (harness) │    │    (format)  │    │    File      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

1. **Open Instance** — Acquire an exclusive session on the document
2. **Queue** — Redis queue serializes all mutations with document-level locking
3. **Change** — Agent harness reads the file, decides edits, and applies them with real tools
4. **Pretty** — Format-specific normalization (styles, heading hierarchy, spacing)
5. **Get File** — Download the result in any supported format

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI + Uvicorn (Python) |
| **Database** | PostgreSQL 16 + pgvector |
| **Queue / Cache** | Redis 7 (task dispatch, locking, pub/sub) |
| **Frontend** | Next.js 15 + React + Tailwind CSS |
| **Vision** | Google Gemini API |
| **LLM** | OpenAI GPT-4o + Gemini fallback |
| **Document Drivers** | LibreOffice, Rust native (PyO3), Mock |

## Quick Links

- **[Quick Start](/docs/getting-started/quickstart)** — Get running in under 5 minutes with Docker
- **[Architecture](/docs/architecture/overview)** — Deep dive into the system design
- **[Features](/docs/features/ingestion)** — Explore each capability in detail
- **[API Reference](/docs/api-reference/endpoints)** — Full endpoint documentation
- **[Guides](/docs/guides/upload-first-document)** — Step-by-step tutorials
