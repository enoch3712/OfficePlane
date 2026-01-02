# OfficePlane

Enterprise-grade agentic runtime for Office artifacts (Render Plane v0.1).

## Quickstart (Docker)
```bash
docker build -t officeplane -f docker/Dockerfile .
docker run --rm -p 8001:8001 officeplane
curl -F "file=@your.pptx" "http://localhost:8001/render?dpi=120&output=both&inline=true"
```

## Self-contained tests (no LibreOffice needed)
```bash
pip install -e ".[dev]"
pytest -q
```

## Full fidelity (LibreOffice)
Run in Docker (recommended). LibreOffice is included in the image.
