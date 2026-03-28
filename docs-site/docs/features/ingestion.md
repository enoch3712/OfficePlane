---
sidebar_position: 1
title: Document Ingestion
---

# Document Ingestion

OfficePlane's ingestion pipeline converts uploaded files (DOCX, PDF) into a rich, hierarchical document model using AI vision. The result is a structured representation stored in PostgreSQL with pgvector embeddings for semantic search.

## Pipeline Overview

```
Upload ──> Format     ──> PDF         ──> Page        ──> Image       ──> Vision      ──> Structure  ──> Storage
           Detection      Conversion      Rendering      Compression     Analysis       Parsing        (Postgres)
```

### Step 1: Format Detection

Magic byte detection identifies the file type — no reliance on file extensions.

| Format | Magic Bytes | Detected As |
|--------|-------------|-------------|
| PDF | `%PDF` | PDF |
| DOCX | `PK` (ZIP with `word/document.xml`) | DOCX |
| PPTX | `PK` (ZIP with `ppt/presentation.xml`) | PPTX |
| XLSX | `PK` (ZIP with `xl/workbook.xml`) | XLSX |

### Step 2: PDF Conversion

Non-PDF files are converted via the active driver:

```python
# LibreOffice driver (Docker)
driver.convert(input_path, output_format="pdf")

# Rust driver (native, faster)
driver.convert(input_path, output_format="pdf")
```

:::info
DOCX-to-PDF conversion requires LibreOffice, which is available in the Docker container. Local development without LibreOffice can only ingest PDFs directly.
:::

### Step 3: Page Rendering

PDF pages are rendered to images using PyMuPDF (fitz):

```python
# Each page becomes a PNG/JPEG image
for page in pdf_document:
    pixmap = page.get_pixmap(dpi=150)
    images.append(pixmap.tobytes("png"))
```

### Step 4: Image Compression

Images are compressed to a target size (default: 75KB) using Pillow. This reduces API costs and latency without sacrificing vision model accuracy:

```python
compress_image(image_bytes, target_kb=75)
```

### Step 5: Vision Analysis

Page images are sent to Gemini in batches for structure extraction:

```python
# Batched vision API calls (default: 8 pages per batch)
for batch in chunk(images, batch_size=8):
    response = gemini.analyze(batch, prompt=EXTRACTION_PROMPT)
```

The vision model returns structured JSON describing the document's hierarchy, content, and formatting.

### Step 6: Structure Parsing

The JSON response is parsed into the document model:

```
Document (title, author, metadata)
├── Chapter (title, order_index, summary)
│   └── Section (title, order_index)
│       └── Page (page_number, content, word_count)
│           └── Chunk (text, embedding, offset)
```

### Step 7: Storage

Everything is persisted to PostgreSQL:
- Document hierarchy in relational tables
- Text chunks with OpenAI embeddings in pgvector for semantic search
- Original file bytes stored for re-download

## API

```bash
# Upload and ingest a document
curl -X POST http://localhost:8001/api/documents/upload \
  -F "file=@my-document.docx"

# Response includes the full document hierarchy
{
  "id": "abc-123",
  "title": "My Document",
  "chapters": [
    {
      "title": "Introduction",
      "sections": [
        {
          "title": "Background",
          "pages": [
            { "page_number": 1, "content": "...", "word_count": 342 }
          ]
        }
      ]
    }
  ]
}
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OFFICEPLANE_INGESTION_VISION_PROVIDER` | Vision provider | `gemini` |
| `OFFICEPLANE_INGESTION_VISION_MODEL` | Model name | `gemini-3-flash-preview` |
| `OFFICEPLANE_INGESTION_BATCH_SIZE` | Pages per batch | `8` |
| `OFFICEPLANE_INGESTION_IMAGE_SIZE_KB` | Target image size | `75` |

Set the provider to `mock` for testing without API calls.

## Checking Ingested Data

```bash
# List all documents
docker exec officeplane-db psql -U officeplane -d officeplane \
  -c "SELECT id, title, created_at FROM documents;"

# View page content
docker exec officeplane-db psql -U officeplane -d officeplane \
  -c "SELECT page_number, LEFT(content, 100) FROM pages ORDER BY page_number;"
```
