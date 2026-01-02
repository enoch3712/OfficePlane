from fastapi.testclient import TestClient
from officeplane.api.main import create_app

def test_render_with_mock_driver(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_DRIVER", "mock")
    monkeypatch.setenv("OUTPUT_MODE", "inline")

    app = create_app()
    client = TestClient(app)

    file_bytes = b"fake_pptx_bytes"
    files = {"file": ("deck.pptx", file_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}

    r = client.post("/render?dpi=120&output=both&inline=true&image_format=png", files=files)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["manifest"]["pages_count"] == 2
    assert len(payload["pages"]) == 2
    assert payload["pdf"]["base64"] is not None
