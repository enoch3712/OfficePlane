# OfficePlane - Development Guide

## Quick Start for Development

### Option A: Docker with Hot Reload (Recommended)
Source code is mounted into the container, so code changes auto-reload without rebuilding.

```bash
# Start all services (first time or after docker-compose.yml changes)
docker compose up -d

# Install Pillow (first time only after image rebuild)
docker exec officeplane-api pip install Pillow

# View API logs
docker logs -f officeplane-api
```

Code changes in `src/` are immediately reflected (uvicorn --reload is enabled).

### Option B: Full Docker Rebuild (when dependencies change)
Only needed when pyproject.toml or Dockerfile changes:
```bash
docker compose build api --no-cache
docker compose up -d api
docker exec officeplane-api pip install Pillow
```

### Access the Application
- UI: http://localhost:3000
- API: http://localhost:8001
- API Docs: http://localhost:8001/docs

## Architecture Overview

### Document Ingestion Pipeline
1. **Format Detection** - Detect PDF/DOCX/etc.
2. **PDF Conversion** - DOCX → PDF via LibreOffice (in Docker only)
3. **Page Rendering** - PDF → Images via PyMuPDF
4. **Image Compression** - Optimize for vision API via Pillow
5. **Vision Analysis** - Extract structure via Gemini API (batched)
6. **Structure Parsing** - JSON → Document/Chapter/Section/Page models
7. **Storage** - PostgreSQL with pgvector

### Key Files
- `src/officeplane/api/management_routes.py` - Document upload API
- `src/officeplane/ingestion/ingestion_service.py` - Vision ingestion orchestrator
- `src/officeplane/ingestion/vision_adapters/gemini.py` - Gemini vision adapter
- `src/officeplane/ingestion/prompts.py` - Vision model prompts
- `src/officeplane/ingestion/structure_parser.py` - JSON to model parser
- `src/officeplane/ingestion/config.py` - Ingestion configuration

### Environment Variables
```
GOOGLE_API_KEY=<your-gemini-api-key>
DATABASE_URL=postgresql://officeplane:officeplane@localhost:5433/officeplane
OFFICEPLANE_DRIVER=libreoffice
OFFICEPLANE_INGESTION_VISION_PROVIDER=gemini  # or "mock" for testing
OFFICEPLANE_INGESTION_VISION_MODEL=gemini-3-flash-preview
OFFICEPLANE_INGESTION_BATCH_SIZE=8
OFFICEPLANE_INGESTION_IMAGE_SIZE_KB=75
```

## Database

### PostgreSQL with pgvector
- Host: localhost:5433 (mapped from Docker)
- Database: officeplane
- User: officeplane
- Password: officeplane

### Check Data
```bash
docker exec officeplane-db psql -U officeplane -d officeplane -c "SELECT * FROM documents;"
docker exec officeplane-db psql -U officeplane -d officeplane -c "SELECT page_number, LEFT(content, 100) FROM pages ORDER BY page_number;"
```

## Testing

### Run Tests
```bash
pytest tests/
```

### Test Document
Use: `Chapter 4 - AI Ethics Safety and Compliance_mcq 1.docx` (14 pages)

## Common Issues

### LibreOffice Error Locally
When running API locally, LibreOffice pool errors are expected. DOCX→PDF conversion only works in Docker where LibreOffice is installed. For local testing with DOCX files, either:
1. Use Docker for the API: `docker compose up -d`
2. Convert DOCX to PDF manually first

### Missing Pillow
```bash
pip install Pillow
```

### Missing GOOGLE_API_KEY
Set in `.env` file or export directly.

## Full Docker Setup (slower but complete)
```bash
docker compose up -d
docker exec officeplane-api pip install Pillow  # First time only after rebuild
```

## Rebuild Docker (when needed)
```bash
docker compose build api --no-cache
docker compose up -d api
docker exec officeplane-api pip install Pillow
```
