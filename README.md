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

## License

MIT
