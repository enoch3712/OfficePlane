"""Tests for the DeepSeek text-based structure adapter (Phase 9)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from officeplane.ingestion.structure_adapters import DeepSeekStructureAdapter


@pytest.mark.asyncio
async def test_analyze_calls_litellm_and_parses_json():
    adapter = DeepSeekStructureAdapter()
    fake_response = MagicMock()
    fake_response.choices = [
        MagicMock(message=MagicMock(content='{"title": "T", "chapters": []}'))
    ]
    with patch(
        "officeplane.ingestion.structure_adapters.deepseek.litellm.acompletion",
        new=AsyncMock(return_value=fake_response),
    ):
        out = await adapter.analyze(
            [{"page_number": 1, "text": "hi"}], filename="x.pptx"
        )
    assert out["title"] == "T"
    assert out["chapters"] == []


@pytest.mark.asyncio
async def test_analyze_chunks_long_inputs():
    adapter = DeepSeekStructureAdapter(max_pages_per_call=2)
    fake_response = MagicMock()
    fake_response.choices = [
        MagicMock(message=MagicMock(content='{"title": "Part", "chapters": [{"title": "C", "sections": [{"title":"S","pages":[]}]}]}'))
    ]
    with patch(
        "officeplane.ingestion.structure_adapters.deepseek.litellm.acompletion",
        new=AsyncMock(return_value=fake_response),
    ) as mock_litellm:
        pages = [{"page_number": i, "text": "..."} for i in range(1, 6)]
        out = await adapter.analyze(pages, filename="long.pdf")
    # 5 pages, max 2 per call -> 3 calls
    assert mock_litellm.call_count == 3
    # Merged chapters across 3 chunks of identical content
    assert len(out["chapters"]) == 3
