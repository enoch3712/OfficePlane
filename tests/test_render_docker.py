import os
import httpx
import pytest
from pathlib import Path

TESTS_DIR = Path(__file__).parent
TEST_PPTX = TESTS_DIR / "test.pptx"

@pytest.fixture
def api_url():
    """Returns the URL of the running OfficePlane service."""
    return os.getenv("OFFICEPLANE_URL", "http://localhost:8001")

def test_render_real_pptx_docker(api_url):
    """
    Test rendering a real PPTX file against a running Docker container (or any remote instance).
    
    To run this:
    1. docker build -t officeplane -f docker/Dockerfile .
    2. docker run --rm -p 8001:8001 officeplane
    3. pytest tests/test_render_docker.py
    """
    assert TEST_PPTX.exists(), f"Missing test file: {TEST_PPTX}"

    with open(TEST_PPTX, "rb") as f:
        files = {
            "file": (
                "test.pptx", 
                f, 
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
        }
        # LibreOffice conversion can be slow, so we use a generous timeout
        response = httpx.post(
            f"{api_url}/render?dpi=120&output=both&inline=true&image_format=png", 
            files=files,
            timeout=60.0
        )

    assert response.status_code == 200, response.text
    payload = response.json()

    # Basic manifest validation
    assert "manifest" in payload
    assert payload["manifest"]["pages_count"] > 0
    assert "pages" in payload
    assert len(payload["pages"]) == payload["manifest"]["pages_count"]
    
    # PDF check
    assert "pdf" in payload
    assert payload["pdf"]["base64"] is not None
    
    # Input metadata
    assert payload["input"]["filename"] == "test.pptx"
    assert payload["input"]["size_bytes"] > 0

    # Page structure validation
    for page in payload["pages"]:
        for field in ["page", "dpi", "width", "height", "sha256", "base64"]:
            assert field in page, f"Missing field {field} in page {page.get('page')}"
        assert page["dpi"] == 120
        assert len(page["base64"]) > 0

