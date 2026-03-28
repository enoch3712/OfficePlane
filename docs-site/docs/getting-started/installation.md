---
sidebar_position: 2
title: Installation
---

# Installation

OfficePlane can be run via Docker (recommended) or locally for development.

## Option A: Docker (Recommended)

Docker handles all dependencies — PostgreSQL, Redis, LibreOffice, and Python packages.

```bash
git clone https://github.com/officeplane/officeplane
cd officeplane
docker compose up -d
```

Source code is **mounted into the container**, so code changes auto-reload without rebuilding.

### First-time setup

```bash
# Install Pillow for image processing (first time after build)
docker exec officeplane-api pip install Pillow
```

### View logs

```bash
docker logs -f officeplane-api
```

### Rebuild (when dependencies change)

Only needed when `pyproject.toml` or `Dockerfile` changes:

```bash
docker compose build api --no-cache
docker compose up -d api
docker exec officeplane-api pip install Pillow
```

## Option B: Local Development

### Requirements

- Python 3.10+
- Node.js 18+
- PostgreSQL 16 with pgvector extension
- Redis 7
- LibreOffice (for DOCX-to-PDF conversion)

### Backend

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run the API server
uvicorn officeplane.api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd ui
npm install
npm run dev
```

The UI runs at http://localhost:3000.

:::warning LibreOffice Required for DOCX
When running the API locally without LibreOffice installed, DOCX-to-PDF conversion will fail. Either install LibreOffice or use Docker for the API service.
:::

## Services Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    docker compose up -d                      │
├──────────────┬───────────────┬──────────────┬───────────────┤
│   API        │   UI          │   PostgreSQL │   Redis       │
│   :8001      │   :3000       │   :5433      │   :6379       │
│   FastAPI    │   Next.js     │   pgvector   │   Queue +     │
│   + Workers  │   + React     │   + embeddings│  Pub/Sub     │
└──────────────┴───────────────┴──────────────┴───────────────┘
```
