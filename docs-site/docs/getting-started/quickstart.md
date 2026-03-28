---
sidebar_position: 1
title: Quick Start
---

# Quick Start

Get OfficePlane running locally in under 5 minutes using Docker.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A [Google Gemini API key](https://ai.google.dev/) (for document ingestion)

## 1. Clone and Configure

```bash
git clone https://github.com/officeplane/officeplane
cd officeplane
```

Create a `.env` file in the project root:

```bash
GOOGLE_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key    # optional, for content generation
```

## 2. Start Services

```bash
docker compose up -d
```

This starts four services:

| Service | URL | Purpose |
|---------|-----|---------|
| **UI** | http://localhost:3000 | Next.js frontend dashboard |
| **API** | http://localhost:8001 | FastAPI backend |
| **PostgreSQL** | localhost:5433 | Document storage + pgvector |
| **Redis** | localhost:6379 | Task queue + pub/sub |

## 3. Install Pillow (first time only)

```bash
docker exec officeplane-api pip install Pillow
```

## 4. Verify

```bash
# Check API health
curl http://localhost:8001/health

# Open the dashboard
open http://localhost:3000
```

## 5. Upload Your First Document

```bash
curl -X POST http://localhost:8001/api/documents/upload \
  -F "file=@path/to/your-document.docx"
```

Or use the **Upload** button in the UI dashboard.

The ingestion pipeline will:
1. Detect the file format (DOCX/PDF)
2. Convert to PDF if needed (via LibreOffice)
3. Render each page to an image
4. Send images to Gemini vision for structure extraction
5. Parse the result into a document hierarchy
6. Store everything in PostgreSQL with vector embeddings

## What's Next

- **[Upload your first document](/docs/guides/upload-first-document)** — Full walkthrough with screenshots
- **[Generate a presentation](/docs/guides/generate-presentation)** — Create content from a prompt
- **[Configuration](/docs/getting-started/configuration)** — Tune environment variables
