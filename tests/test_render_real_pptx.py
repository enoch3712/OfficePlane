import os
from pathlib import Path

from fastapi.testclient import TestClient

from officeplane.api.main import create_app

TESTS_DIR = Path(__file__).parent
TEST_PPTX = TESTS_DIR / "test.pptx"


def test_render_real_pptx_local():
    """Test rendering a real pptx file using the local app and mock driver."""
    assert TEST_PPTX.exists(), f"Missing test file: {TEST_PPTX}"

    app = create_app()
    client = TestClient(app)

    with open(TEST_PPTX, "rb") as f:
        files = {"file": ("test.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        r = client.post("/render?dpi=120&output=both&inline=true&image_format=png", files=files)

    assert r.status_code == 200, r.text
    payload = r.json()

    # Mock driver always returns 2 pages
    assert payload["manifest"]["pages_count"] == 2
    assert len(payload["pages"]) == 2
    assert payload["pdf"]["base64"] is not None
    assert payload["input"]["filename"] == "test.pptx"
    assert payload["input"]["size_bytes"] > 0

    # Verify each page has expected fields
    for page in payload["pages"]:
        assert "page" in page
        assert "dpi" in page
        assert "width" in page
        assert "height" in page
        assert "sha256" in page
        assert "base64" in page
