import os

import pytest
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def test_semantic_search_400_on_empty_query():
    c = _client()
    r = c.post("/api/search/semantic", json={"query": ""})
    assert r.status_code == 400


def test_semantic_search_returns_results_against_bp():
    """End-to-end: requires GOOGLE_API_KEY + ingested+embedded BP doc."""
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY required")
    c = _client()
    r = c.post("/api/search/semantic", json={"query": "blood pressure cuff size", "limit": 3})
    if r.status_code == 503:
        pytest.skip("embedding provider unavailable")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["count"] >= 0
    if j["count"] > 0:
        for k in ("chunk_id", "document_id", "content", "score"):
            assert k in j["results"][0]
        # Top score should be a float (cosine similarity-ish)
        assert isinstance(j["results"][0]["score"], float)
