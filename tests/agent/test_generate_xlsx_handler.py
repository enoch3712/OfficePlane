"""Tests for the generate-xlsx skill handler."""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/generate-xlsx/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/generate-xlsx/handler.py"
    spec = importlib.util.spec_from_file_location("gx_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gx_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _llm(json_str: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json_str))])


def test_validates_inputs():
    mod = _load_handler()

    async def _run(inputs):
        return await mod.execute(inputs=inputs)

    with pytest.raises(ValueError, match="source_document_ids"):
        asyncio.run(_run({"source_document_ids": [], "brief": "x"}))

    with pytest.raises(ValueError, match="brief"):
        asyncio.run(_run({"source_document_ids": ["doc-1"], "brief": ""}))


def test_handler_renders_real_xlsx(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))

    fake_json = json.dumps({
        "type": "workbook",
        "schema_version": "1.0",
        "meta": {"title": "BP Checklist Workbook", "author": None, "description": None, "render_hints": {}},
        "sheets": [
            {
                "id": "sh1",
                "name": "BP Measurements",
                "freeze_header": True,
                "column_widths": {},
                "sections": [
                    {"type": "title", "id": "t1", "text": "Blood Pressure Measurements", "span_columns": 4},
                    {"type": "kpi", "id": "k1", "label": "Avg Systolic", "value": 122, "format": "number"},
                    {
                        "type": "table",
                        "id": "tbl1",
                        "name": "BPData",
                        "headers": ["Date", "Systolic", "Diastolic", "Pulse"],
                        "rows": [
                            ["2024-01-01", 120, 80, 72],
                            ["2024-01-02", 122, 82, 74],
                            ["2024-01-03", 118, 78, 70],
                        ],
                        "column_formats": ["date", "integer", "integer", "integer"],
                        "totals_row": None,
                        "autofilter": True,
                        "style": "TableStyleMedium2",
                    },
                ],
            }
        ],
        "attributions": [
            {
                "node_id": "tbl1",
                "document_id": "doc-1",
                "document_title": "BP Source",
                "section_id": None,
                "page_numbers": [],
            }
        ],
    })

    async def _run():
        with patch.object(mod, "_load_sources", new=AsyncMock(return_value=[
            {"document_id": "doc-1", "title": "BP Source", "summary": "BP data", "topics": [], "chapters": []}
        ])):
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(fake_json))):
                with patch.object(mod, "persist_initial_revision", new=AsyncMock(return_value=None)):
                    with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                        return await mod.execute(inputs={
                            "source_document_ids": ["doc-1"],
                            "brief": "BP measurement checklist as a structured workbook with KPI cards",
                        })

    result = asyncio.run(_run())

    assert result["file_path"].endswith("output.xlsx")
    out = Path(result["file_path"])
    assert out.exists(), f"output.xlsx not found at {out}"
    assert out.stat().st_size > 1000, "output.xlsx is suspiciously small"

    # Validate it's a real xlsx (ZIP magic)
    raw = out.read_bytes()
    assert raw[:2] == b"PK", "output.xlsx doesn't start with ZIP magic"

    assert result["title"] == "BP Checklist Workbook"
    assert result["sheet_count"] == 1
    assert result["table_count"] == 1
    assert result["chart_count"] == 0
    assert result["source_document_ids"] == ["doc-1"]

    # Verify document.json was written
    doc_json = out.parent / "document.json"
    assert doc_json.exists()
    stored = json.loads(doc_json.read_text())
    assert stored["type"] == "workbook"
