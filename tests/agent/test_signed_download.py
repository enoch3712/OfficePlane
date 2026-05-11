import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WORKSPACES_ROOT = Path("/data/workspaces")


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def _seed_workspace(workspace_id: str, filename: str = "output.docx") -> Path:
    ws = WORKSPACES_ROOT / workspace_id
    ws.mkdir(parents=True, exist_ok=True)
    p = ws / filename
    p.write_bytes(b"%PDF-fake-or-docx-bytes-for-test" + b"\x00" * 100)
    return p


def test_sign_returns_url_for_real_file():
    c = _client()
    ws_id = str(uuid.uuid4())
    _seed_workspace(ws_id, "output.docx")
    try:
        r = c.post(f"/api/workspaces/{ws_id}/sign", json={"file": "output.docx", "ttl_seconds": 300})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["workspace_id"] == ws_id
        assert j["file"] == "output.docx"
        assert "token=" in j["download_url"]
        assert "exp=" in j["download_url"]
        assert j["expires_at"] > int(time.time())
    finally:
        (WORKSPACES_ROOT / ws_id / "output.docx").unlink(missing_ok=True)


def test_sign_404_when_workspace_missing():
    c = _client()
    r = c.post(f"/api/workspaces/{uuid.uuid4()}/sign", json={"file": "output.docx"})
    assert r.status_code == 404


def test_sign_404_when_file_missing():
    c = _client()
    ws_id = str(uuid.uuid4())
    (WORKSPACES_ROOT / ws_id).mkdir(parents=True, exist_ok=True)
    try:
        r = c.post(f"/api/workspaces/{ws_id}/sign", json={"file": "missing.docx"})
        assert r.status_code == 404
    finally:
        try:
            (WORKSPACES_ROOT / ws_id).rmdir()
        except OSError:
            pass


def test_sign_rejects_path_traversal():
    c = _client()
    ws_id = str(uuid.uuid4())
    (WORKSPACES_ROOT / ws_id).mkdir(parents=True, exist_ok=True)
    try:
        for bad in ["../../etc/passwd", "subdir/file.docx", "..\\windows"]:
            r = c.post(f"/api/workspaces/{ws_id}/sign", json={"file": bad})
            assert r.status_code == 400, f"expected 400 for {bad!r}, got {r.status_code}"
    finally:
        try:
            (WORKSPACES_ROOT / ws_id).rmdir()
        except OSError:
            pass


def test_download_serves_file_with_valid_signature():
    c = _client()
    ws_id = str(uuid.uuid4())
    _seed_workspace(ws_id, "output.docx")
    try:
        r = c.post(f"/api/workspaces/{ws_id}/sign", json={"file": "output.docx", "ttl_seconds": 300})
        j = r.json()
        # Extract token + exp from download_url
        url = j["download_url"]
        q = url.split("?", 1)[1]
        params = dict(p.split("=", 1) for p in q.split("&"))
        d = c.get(f"/api/workspaces/{ws_id}/download/output.docx",
                  params={"token": params["token"], "exp": params["exp"]})
        assert d.status_code == 200, d.text
        assert d.content[:5] == b"%PDF-"
        # Should set the right content-type
        assert "officedocument" in d.headers.get("content-type", "") or "octet-stream" in d.headers.get("content-type", "")
    finally:
        (WORKSPACES_ROOT / ws_id / "output.docx").unlink(missing_ok=True)


def test_download_403_with_bad_token():
    c = _client()
    ws_id = str(uuid.uuid4())
    _seed_workspace(ws_id, "output.docx")
    try:
        future = int(time.time()) + 300
        r = c.get(f"/api/workspaces/{ws_id}/download/output.docx",
                  params={"token": "deadbeef" * 8, "exp": future})
        assert r.status_code == 403
    finally:
        (WORKSPACES_ROOT / ws_id / "output.docx").unlink(missing_ok=True)


def test_download_410_when_expired():
    c = _client()
    ws_id = str(uuid.uuid4())
    _seed_workspace(ws_id, "output.docx")
    try:
        # Build a signed URL manually with past expiry
        from officeplane.api.signed_download import _sign
        past = int(time.time()) - 10
        token = _sign(ws_id, "output.docx", past)
        r = c.get(f"/api/workspaces/{ws_id}/download/output.docx",
                  params={"token": token, "exp": past})
        assert r.status_code == 410
    finally:
        (WORKSPACES_ROOT / ws_id / "output.docx").unlink(missing_ok=True)


def test_download_rejects_traversal_in_filename():
    c = _client()
    ws_id = str(uuid.uuid4())
    (WORKSPACES_ROOT / ws_id).mkdir(parents=True, exist_ok=True)
    try:
        # Even with valid-looking signature, the filename validator catches it.
        # FastAPI may URL-decode the encoded slashes and route to the handler (400)
        # or resolve a different path pattern entirely (404). Both mean "not served".
        r = c.get(f"/api/workspaces/{ws_id}/download/..%2F..%2Fetc%2Fpasswd",
                  params={"token": "x", "exp": int(time.time()) + 60})
        assert r.status_code in (400, 404), f"expected 400 or 404, got {r.status_code}"
    finally:
        try:
            (WORKSPACES_ROOT / ws_id).rmdir()
        except OSError:
            pass
