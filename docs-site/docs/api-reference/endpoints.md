---
sidebar_position: 1
title: Endpoints Overview
---

# API Endpoints Overview

OfficePlane exposes a REST API at `http://localhost:8001`. All endpoints return JSON. The API docs are also available as interactive Swagger at `http://localhost:8001/docs`.

## Base URL

```
http://localhost:8001
```

## Endpoint Groups

| Group | Base Path | Description |
|-------|-----------|-------------|
| [Documents](/docs/api-reference/documents) | `/api/documents` | Upload, list, read, edit, download, plan, execute, verify |
| [Instances](/docs/api-reference/instances) | `/api/instances` | Open/close document sessions |
| [Tasks](/docs/api-reference/tasks) | `/api/tasks` | Queue management, cancel, retry |
| [Generation](/docs/api-reference/generation) | `/api/generate` | Async content generation with SSE |
| [Teams](/docs/api-reference/teams) | `/api/teams` | Multi-agent team orchestration |
| System | `/health`, `/metrics` | Health checks and Prometheus metrics |
| Real-time | `/ws` | WebSocket for live updates |

## Authentication

OfficePlane does not currently require authentication for API calls. Authentication and multi-tenancy are on the roadmap.

## Common Response Patterns

### Success

```json
{
  "id": "uuid",
  "status": "ok",
  ...
}
```

### Error

```json
{
  "detail": "Document not found",
  "status_code": 404
}
```

### Async Job (202 Accepted)

```json
{
  "job_id": "gen-abc-123",
  "status": "queued",
  "stream_url": "/api/generate/gen-abc-123/stream"
}
```

## Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload and ingest a document |
| `GET` | `/api/documents` | List all documents |
| `GET` | `/api/documents/{id}` | Get document with hierarchy |
| `DELETE` | `/api/documents/{id}` | Delete a document |
| `GET` | `/api/documents/{id}/download` | Download in any format |
| `POST` | `/api/documents/{id}/plan` | Generate action plan |
| `POST` | `/api/documents/{id}/execute` | Execute action plan |
| `POST` | `/api/documents/{id}/verify` | Verify changes match intent |
| `POST` | `/api/instances` | Open document instance |
| `GET` | `/api/instances` | List instances |
| `POST` | `/api/instances/{id}/close` | Close instance |
| `POST` | `/api/tasks` | Create task |
| `GET` | `/api/tasks` | List tasks |
| `POST` | `/api/tasks/{id}/cancel` | Cancel task |
| `POST` | `/api/tasks/{id}/retry` | Retry failed task |
| `POST` | `/api/generate` | Start generation job |
| `GET` | `/api/generate/{id}/stream` | SSE stream |
| `GET` | `/api/generate/{id}` | Job status |
| `DELETE` | `/api/generate/{id}` | Cancel job |
| `POST` | `/api/teams` | Start agent team |
| `GET` | `/api/teams/{id}/stream` | Team SSE stream |
| `GET` | `/api/teams/{id}` | Team status |
| `DELETE` | `/api/teams/{id}` | Cancel team |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |
