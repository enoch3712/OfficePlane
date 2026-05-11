import json
from unittest.mock import patch, AsyncMock
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def _llm(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_400_on_empty_query():
    c = _client()
    r = c.post("/api/chat/grounded", json={"query": ""})
    assert r.status_code == 400


def test_grounded_path_returns_citations(monkeypatch):
    """When retrieval returns passages, we get mode='grounded' + citations."""
    c = _client()

    fake_search = {
        "results": [
            {"chunk_id": "c-1", "document_id": "d-1", "content": "Cuff size matters.", "score": 0.92},
            {"chunk_id": "c-2", "document_id": "d-1", "content": "Arm at heart level.", "score": 0.88},
        ]
    }

    class FakeResponse:
        status_code = 200
        def json(self):
            return fake_search

    class FakeAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            assert "/api/search/semantic" in url
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with patch("litellm.acompletion", new=AsyncMock(return_value=_llm("Use the correct cuff size [1] and position arm at heart level [2]."))):
        with patch("officeplane.api.chat_routes.persist_skill_invocation", new=AsyncMock(return_value=None)):
            r = c.post("/api/chat/grounded", json={"query": "how to measure BP?"})

    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "grounded"
    assert j["retrieval_count"] == 2
    assert len(j["citations"]) == 2
    assert j["citations"][0]["index"] == 1
    assert "[1]" in j["answer"]


def test_ungrounded_fallback_when_search_fails(monkeypatch):
    """When search endpoint 503s, we still answer but mark mode='ungrounded'."""
    c = _client()

    class FakeAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            raise httpx.ConnectError("fake connection failure")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with patch("litellm.acompletion", new=AsyncMock(return_value=_llm("I can't ground my answer in your documents — generally, BP is measured with a cuff."))):
        with patch("officeplane.api.chat_routes.persist_skill_invocation", new=AsyncMock(return_value=None)):
            r = c.post("/api/chat/grounded", json={"query": "what is BP?"})

    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "ungrounded"
    assert j["retrieval_count"] == 0
    assert j["citations"] == []
    assert isinstance(j["answer"], str) and len(j["answer"]) > 0


def test_scope_passes_through(monkeypatch):
    """When document_ids or collection_id is given, it is forwarded to /api/search/semantic."""
    c = _client()
    captured = {}

    class FakeResp:
        status_code = 200
        def json(self): return {"results": []}

    class FakeAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            captured["payload"] = json
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with patch("litellm.acompletion", new=AsyncMock(return_value=_llm("no info."))):
        with patch("officeplane.api.chat_routes.persist_skill_invocation", new=AsyncMock(return_value=None)):
            c.post("/api/chat/grounded", json={"query": "x", "document_ids": ["a", "b"]})

    assert captured["payload"]["document_ids"] == ["a", "b"]
    assert "collection_id" not in captured["payload"]

    with patch("litellm.acompletion", new=AsyncMock(return_value=_llm("no info."))):
        with patch("officeplane.api.chat_routes.persist_skill_invocation", new=AsyncMock(return_value=None)):
            c.post("/api/chat/grounded", json={"query": "x", "collection_id": "col-1"})

    assert captured["payload"]["collection_id"] == "col-1"
    assert "document_ids" not in captured["payload"]
