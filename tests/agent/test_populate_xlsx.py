import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/populate-xlsx-from-source/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/populate-xlsx-from-source/handler.py"
    spec = importlib.util.spec_from_file_location("px_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["px_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_template(tmp_path: Path, template_id: str = "tpl-1") -> Path:
    tpl = {
        "template_id": template_id,
        "name": "Q3 Sales Template",
        "workbook": {
            "type": "workbook", "meta": {"title": "Q3 Sales"},
            "sheets": [{
                "id": "s1", "name": "Summary", "sections": [
                    {"type": "title", "text": "Q3"},
                    {"type": "table", "id": "tab1", "name": "Revenue",
                     "headers": ["Region", "Revenue", "Growth"],
                     "rows": [],
                     "column_formats": ["text", "currency_usd", "percent"]},
                    {"type": "table", "id": "tab2", "name": "Forecast",
                     "headers": ["Quarter", "Projected"],
                     "rows": [],
                     "column_formats": ["text", "currency_usd"]},
                ]
            }],
            "attributions": [],
        },
    }
    root = tmp_path / "templates"
    root.mkdir(parents=True, exist_ok=True)
    p = root / f"{template_id}.json"
    p.write_text(json.dumps(tpl))
    return p


def test_validates_inputs(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("OFFICEPLANE_TEMPLATES_ROOT", str(tmp_path / "templates"))
    async def _run(i): return await mod.execute(inputs=i)
    with pytest.raises(ValueError, match="source_document_ids"):
        asyncio.run(_run({"template_id": "x"}))
    with pytest.raises(ValueError, match="template_id"):
        asyncio.run(_run({"source_document_ids": ["a"]}))


def test_missing_template(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("OFFICEPLANE_TEMPLATES_ROOT", str(tmp_path / "templates"))
    with pytest.raises(FileNotFoundError):
        asyncio.run(mod.execute(inputs={
            "source_document_ids": ["d1"], "template_id": "nope",
        }))


def test_fuzzy_header_mapping(tmp_path, monkeypatch):
    """Extracted table with headers "Region/Revenue/Growth" should map to template's "Revenue" table."""
    mod = _load_handler()
    monkeypatch.setenv("OFFICEPLANE_TEMPLATES_ROOT", str(tmp_path / "templates"))
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path / "ws"))
    _seed_template(tmp_path)

    # Mock the sibling handlers
    fake_extract = AsyncMock(return_value={
        "tables": [
            {"name": "Q3 Regional", "headers": ["Region", "Revenue", "Growth"],
             "rows": [["NA", 1200, 0.12], ["EU", 900, 0.08]]},
            {"name": "Forecast Numbers", "headers": ["Quarter", "Projected"],
             "rows": [["Q4", 3500]]},
            {"name": "Unrelated", "headers": ["Foo", "Bar"],
             "rows": [["a", "b"]]},
        ]
    })
    fake_apply = AsyncMock(return_value={
        "file_path": "/data/workspaces/abc/output.xlsx",
        "file_url": "/data/workspaces/abc/output.xlsx",
        "title": "Q3 Sales",
        "template_id": "tpl-1",
        "table_count": 2,
        "sheet_count": 1,
    })

    fake_extract_mod = type(sys)("fake_extract_mod"); fake_extract_mod.execute = fake_extract
    fake_apply_mod = type(sys)("fake_apply_mod"); fake_apply_mod.execute = fake_apply

    def fake_loader(skill: str):
        if skill == "extract-tabular-data":
            return fake_extract_mod
        if skill == "xlsx-template-apply":
            return fake_apply_mod
        raise RuntimeError(f"unknown sibling: {skill}")

    async def _run():
        with patch.object(mod, "_load_sibling_handler", side_effect=fake_loader):
            with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                return await mod.execute(inputs={
                    "source_document_ids": ["d1"],
                    "template_id": "tpl-1",
                })

    r = asyncio.run(_run())
    assert r["template_id"] == "tpl-1"
    assert r["source_document_count"] == 1
    assert r["extracted_table_count"] == 3
    # Both template tables filled
    report = {row["template_table"]: row for row in r["mapping_report"]}
    assert report["Revenue"]["filled_from"] == "Q3 Regional"
    assert report["Forecast"]["filled_from"] == "Forecast Numbers"
    # Apply was called with the right payload
    fake_apply.assert_awaited_once()
    apply_call = fake_apply.await_args.kwargs["inputs"]
    assert "Revenue" in apply_call["tables"]
    assert apply_call["tables"]["Revenue"] == [["NA", 1200, 0.12], ["EU", 900, 0.08]]


def test_explicit_mapping_overrides_fuzzy(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("OFFICEPLANE_TEMPLATES_ROOT", str(tmp_path / "templates"))
    _seed_template(tmp_path)

    fake_extract_mod = type(sys)("fem"); fake_extract_mod.execute = AsyncMock(return_value={
        "tables": [
            {"name": "Best Match", "headers": ["Region", "Revenue", "Growth"], "rows": [["x", 1, 0.1]]},
            {"name": "Explicit Choice", "headers": ["Whatever"], "rows": [["forced"]]},
        ]
    })
    fake_apply_mod = type(sys)("fam"); fake_apply_mod.execute = AsyncMock(return_value={
        "file_path": "/p", "file_url": "/u", "title": "T", "template_id": "tpl-1",
    })

    def fake_loader(skill):
        return {"extract-tabular-data": fake_extract_mod,
                "xlsx-template-apply": fake_apply_mod}[skill]

    async def _run():
        with patch.object(mod, "_load_sibling_handler", side_effect=fake_loader):
            with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                return await mod.execute(inputs={
                    "source_document_ids": ["d1"], "template_id": "tpl-1",
                    "mapping": {"Revenue": "Explicit Choice"},
                })

    r = asyncio.run(_run())
    report = {row["template_table"]: row for row in r["mapping_report"]}
    assert report["Revenue"]["filled_from"] == "Explicit Choice"


def test_unmatched_template_table_reported_empty(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("OFFICEPLANE_TEMPLATES_ROOT", str(tmp_path / "templates"))
    _seed_template(tmp_path)

    fake_extract_mod = type(sys)("fem"); fake_extract_mod.execute = AsyncMock(return_value={
        "tables": [
            # Only matches Revenue, nothing matches Forecast
            {"name": "Sales", "headers": ["Region", "Revenue", "Growth"],
             "rows": [["NA", 1000, 0.10]]},
        ]
    })
    fake_apply_mod = type(sys)("fam"); fake_apply_mod.execute = AsyncMock(return_value={
        "file_path": "/p", "file_url": "/u", "title": "T", "template_id": "tpl-1",
    })

    def fake_loader(skill):
        return {"extract-tabular-data": fake_extract_mod,
                "xlsx-template-apply": fake_apply_mod}[skill]

    async def _run():
        with patch.object(mod, "_load_sibling_handler", side_effect=fake_loader):
            with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                return await mod.execute(inputs={
                    "source_document_ids": ["d1"], "template_id": "tpl-1",
                })

    r = asyncio.run(_run())
    report = {row["template_table"]: row for row in r["mapping_report"]}
    assert report["Revenue"]["filled_from"] == "Sales"
    assert report["Forecast"]["filled_from"] is None
    assert report["Forecast"]["row_count"] == 0


def test_raises_when_no_template_tables(tmp_path, monkeypatch):
    mod = _load_handler()
    root = tmp_path / "templates"
    root.mkdir(parents=True, exist_ok=True)
    # Template with no table sections
    (root / "empty-tpl.json").write_text(json.dumps({
        "template_id": "empty-tpl", "name": "Empty",
        "workbook": {"type": "workbook", "meta": {"title": "X"},
                     "sheets": [{"name": "S", "sections": [{"type": "title", "text": "Just a title"}]}]},
    }))
    monkeypatch.setenv("OFFICEPLANE_TEMPLATES_ROOT", str(root))
    with pytest.raises(ValueError, match="no table sections"):
        asyncio.run(mod.execute(inputs={
            "source_document_ids": ["d1"], "template_id": "empty-tpl",
        }))


def test_raises_when_no_matches_anywhere(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("OFFICEPLANE_TEMPLATES_ROOT", str(tmp_path / "templates"))
    _seed_template(tmp_path)
    fake_extract_mod = type(sys)("fem"); fake_extract_mod.execute = AsyncMock(return_value={
        "tables": [{"name": "Wholly Unrelated", "headers": ["Apples", "Pears"], "rows": [["x", "y"]]}],
    })
    fake_apply_mod = type(sys)("fam"); fake_apply_mod.execute = AsyncMock(return_value={})

    def fake_loader(skill):
        return {"extract-tabular-data": fake_extract_mod,
                "xlsx-template-apply": fake_apply_mod}[skill]

    async def _run():
        with patch.object(mod, "_load_sibling_handler", side_effect=fake_loader):
            with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                return await mod.execute(inputs={
                    "source_document_ids": ["d1"], "template_id": "tpl-1",
                })

    with pytest.raises(ValueError, match="no extracted tables matched"):
        asyncio.run(_run())
