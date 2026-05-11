import asyncio
import json
import pytest
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def test_emit_skips_when_callback_none():
    from officeplane.content_agent.streaming import emit
    # Should not raise
    asyncio.run(emit(None, "step", "label"))


def test_emit_calls_sync_callback():
    from officeplane.content_agent.streaming import emit, ProgressEvent
    received: list[ProgressEvent] = []
    asyncio.run(emit(received.append, "loading", "Loading…", count=3))
    assert len(received) == 1
    assert received[0].step == "loading"
    assert received[0].extra["count"] == 3


def test_emit_awaits_async_callback():
    from officeplane.content_agent.streaming import emit, ProgressEvent
    received: list[ProgressEvent] = []

    async def cb(e):
        await asyncio.sleep(0)
        received.append(e)

    asyncio.run(emit(cb, "x", "y"))
    assert received[0].step == "x"


def test_emit_swallows_callback_errors():
    """A buggy callback must not break the handler."""
    from officeplane.content_agent.streaming import emit

    def boom(e):
        raise RuntimeError("kaboom")

    # Should not raise
    asyncio.run(emit(boom, "step", "label"))


def test_stream_404_for_unknown_skill():
    c = _client()
    r = c.post("/api/jobs/stream/nope-skill", json={"inputs": {}})
    assert r.status_code == 404


def test_stream_emits_events_for_real_skill(monkeypatch):
    """End-to-end: invoke the streaming endpoint for generate-docx with mocked LLM.
    Confirm we receive progress + result + done events."""
    c = _client()

    # Mock litellm + sources at the handler module level by patching after load
    import importlib.util, sys
    from pathlib import Path
    handler_path = Path("/app/src/officeplane/content_agent/skills/generate-docx/handler.py")
    if not handler_path.exists():
        handler_path = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/generate-docx/handler.py"
    spec = importlib.util.spec_from_file_location("streamed_handler_generate_docx", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["streamed_handler_generate_docx"] = mod
    spec.loader.exec_module(mod)

    from unittest.mock import AsyncMock, patch
    from types import SimpleNamespace

    fake_resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps({
            "type": "document", "meta": {"title": "T"},
            "children": [{"type": "section", "id": "s1", "level": 1, "heading": "H",
                          "children": [{"type": "paragraph", "id": "p1", "text": "t"}]}],
            "attributions": [],
        })
    ))])

    with patch.object(mod, "_load_sources", new=AsyncMock(return_value=[
        {"document_id": "d", "title": "Src", "summary": "", "topics": [], "chapters": []}
    ])):
        with patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)):
            with patch.object(mod, "persist_initial_revision", new=AsyncMock(return_value=None)):
                with patch.object(mod, "persist_derivations_from_document", new=AsyncMock(return_value=0)):
                    with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                        r = c.post(
                            "/api/jobs/stream/generate-docx",
                            json={"inputs": {"source_document_ids": ["d"], "brief": "x"}},
                        )
                        assert r.status_code == 200
                        body = r.text
                        # Confirm we saw multiple events
                        assert body.count("event: progress") >= 3
                        assert "event: result" in body
                        assert "event: done" in body
