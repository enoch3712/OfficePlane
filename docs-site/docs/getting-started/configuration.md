---
sidebar_position: 3
title: Configuration
---

# Configuration

OfficePlane is configured via environment variables. Set them in a `.env` file or export them directly.

## Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://officeplane:officeplane@localhost:5433/officeplane` |
| `GOOGLE_API_KEY` | Gemini API key for vision ingestion | `AIza...` |

## API Keys

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Gemini API key (ingestion + planning) | *required* |
| `OPENAI_API_KEY` | OpenAI API key (content generation) | *optional* |

## Document Processing

| Variable | Description | Default |
|----------|-------------|---------|
| `OFFICEPLANE_DRIVER` | Document conversion driver | `libreoffice` |
| `OFFICEPLANE_INGESTION_VISION_PROVIDER` | Vision provider for ingestion | `gemini` |
| `OFFICEPLANE_INGESTION_VISION_MODEL` | Gemini model for vision extraction | `gemini-3-flash-preview` |
| `OFFICEPLANE_INGESTION_BATCH_SIZE` | Pages per vision API batch call | `8` |
| `OFFICEPLANE_INGESTION_IMAGE_SIZE_KB` | Target image size for compression | `75` |

### Driver Options

| Driver | Description | Performance |
|--------|-------------|-------------|
| `libreoffice` | Python subprocess pool (unoserver) — Docker only | ~1.1s/doc |
| `rust` | Native PyO3 module — highest performance | ~0.5s/doc |
| `mock` | No-op driver for testing | instant |

## Infrastructure

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `OFFICEPLANE_BROKER` | Queue backend | `redis` |

### Broker Options

| Broker | Description | Use Case |
|--------|-------------|----------|
| `redis` | Production Redis backend | Production, staging |
| `memory` | In-memory queue (no persistence) | Development, testing |

## Content Generation

| Variable | Description | Default |
|----------|-------------|---------|
| `CONTENT_AGENT_MODEL` | LLM model for content generation | `gpt-4o` |
| `CONTENT_AGENT_TIMEOUT` | Generation timeout in seconds | `600` |
| `CONTENT_AGENT_WORKSPACE` | Workspace directory for agent artifacts | `/data/workspaces` |
| `OFFICEPLANE_PLAN_MODEL` | LLM model for plan generation | `gemini-2.0-flash` |

## Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | API base URL for the frontend | `http://localhost:8001` |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL for real-time updates | `ws://localhost:8001` |

## Example `.env`

```bash
# API Keys
GOOGLE_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql://officeplane:officeplane@localhost:5433/officeplane

# Redis
REDIS_URL=redis://localhost:6379/0

# Processing
OFFICEPLANE_DRIVER=libreoffice
OFFICEPLANE_INGESTION_VISION_PROVIDER=gemini
OFFICEPLANE_INGESTION_VISION_MODEL=gemini-3-flash-preview
OFFICEPLANE_INGESTION_BATCH_SIZE=8

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```
