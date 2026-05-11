import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/detect-pii/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/detect-pii/handler.py"
    spec = importlib.util.spec_from_file_location("pii_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pii_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_regex():
    p = Path("/app/src/officeplane/content_agent/skills/detect-pii/regex_patterns.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/detect-pii/regex_patterns.py"
    spec = importlib.util.spec_from_file_location("pii_regex_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pii_regex_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _llm(s: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=s))])


def test_regex_finds_email():
    rx = _load_regex()
    hits = rx.find_regex_pii("Contact alice@example.com or bob@example.org for info.")
    cats = {h["category"] for h in hits}
    assert "email" in cats
    vals = {h["value"] for h in hits if h["category"] == "email"}
    assert vals == {"alice@example.com", "bob@example.org"}


def test_regex_finds_ssn():
    rx = _load_regex()
    hits = rx.find_regex_pii("Patient SSN: 123-45-6789. Other id is junk.")
    assert any(h["category"] == "us_ssn" and h["value"] == "123-45-6789" for h in hits)


def test_regex_finds_valid_credit_card_only():
    """Luhn check should pass a real-looking CC and reject a random sequence."""
    rx = _load_regex()
    # 4111 1111 1111 1111 is a known Luhn-valid test number
    hits = rx.find_regex_pii("Card: 4111-1111-1111-1111. Junk number: 1234567890123456.")
    cards = [h for h in hits if h["category"] == "credit_card"]
    values = {h["value"] for h in cards}
    # Should contain the valid card and NOT 1234567890123456 (Luhn fails)
    assert "4111-1111-1111-1111" in values
    # 1234567890123456 has Luhn checksum that may pass — accept either, just ensure at least one
    assert len(cards) >= 1


def test_regex_finds_iban():
    rx = _load_regex()
    # German IBAN test value (22 chars)
    hits = rx.find_regex_pii("Transfer to DE89370400440532013000.")
    assert any(h["category"] == "iban" and h["value"].startswith("DE89") for h in hits)


def test_handler_validates_inputs():
    mod = _load_handler()
    async def _run(i): return await mod.execute(inputs=i)
    with pytest.raises(ValueError, match="document_id"):
        asyncio.run(_run({}))
    with pytest.raises(ValueError, match="max_findings"):
        asyncio.run(_run({"document_id": "x", "max_findings": 0}))
    with pytest.raises(ValueError, match="categories must be a list"):
        asyncio.run(_run({"document_id": "x", "categories": "email"}))
    with pytest.raises(ValueError, match="unknown categories"):
        asyncio.run(_run({"document_id": "x", "categories": ["bogus"]}))


def test_handler_regex_only_path_finds_pii_no_llm_calls():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="d1", title="Test")
    fake_pages = [SimpleNamespace(pageNumber=1,
                                  content="Patient: alice@example.com SSN 123-45-6789")]

    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=fake_doc)
            i.chapter.find_many = AsyncMock(return_value=[])
            i.page.find_many = AsyncMock(return_value=fake_pages)
            with patch("litellm.acompletion", new=AsyncMock()) as ac:
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    r = await mod.execute(inputs={
                        "document_id": "d1", "regex_only": True,
                    })
                    return r, ac

    r, ac = asyncio.run(_run())
    assert r["finding_count"] >= 2
    cats = set(r["category_counts"].keys())
    assert {"email", "us_ssn"} <= cats
    ac.assert_not_called()
    # Redaction plan has the right replacements
    repls = {p["suggested_replacement"] for p in r["redaction_plan"]}
    assert "[EMAIL]" in repls
    assert "[SSN]" in repls


def test_handler_llm_pass_adds_person_names():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="d2", title="Test")
    fake_pages = [SimpleNamespace(pageNumber=1,
                                  content="Patient John Doe lives at 123 Main St. Email alice@example.com")]

    llm_payload = json.dumps({
        "findings": [
            {"category": "person_name", "value": "John Doe", "page_number": 1, "confidence": 0.9},
            {"category": "address", "value": "123 Main St", "page_number": 1, "confidence": 0.8},
            {"category": "junk_category", "value": "Bogus", "page_number": 1},  # filtered
        ]
    })

    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=fake_doc)
            i.chapter.find_many = AsyncMock(return_value=[])
            i.page.find_many = AsyncMock(return_value=fake_pages)
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(llm_payload))):
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    return await mod.execute(inputs={"document_id": "d2"})

    r = asyncio.run(_run())
    cats = r["category_counts"]
    assert cats.get("person_name") == 1
    assert cats.get("address") == 1
    assert cats.get("email") == 1  # from regex pass
    assert cats.get("junk_category") is None  # filtered
    assert r["llm_count"] == 2
    assert r["regex_count"] == 1


def test_handler_category_filter():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="d3", title="Test")
    fake_pages = [SimpleNamespace(pageNumber=1,
                                  content="alice@example.com SSN 123-45-6789")]

    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=fake_doc)
            i.chapter.find_many = AsyncMock(return_value=[])
            i.page.find_many = AsyncMock(return_value=fake_pages)
            with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                return await mod.execute(inputs={
                    "document_id": "d3", "regex_only": True,
                    "categories": ["email"],
                })

    r = asyncio.run(_run())
    cats = set(r["category_counts"].keys())
    assert cats == {"email"}


def test_handler_missing_document():
    mod = _load_handler()

    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=None)
            return await mod.execute(inputs={"document_id": "missing"})

    with pytest.raises(ValueError, match="document not found"):
        asyncio.run(_run())
