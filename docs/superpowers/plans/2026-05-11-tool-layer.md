# Phase 7 — Tool Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hallucinated SKILL.md outputs with real ones by adding a tool layer (Prisma reads, pgvector search, embeddings, file render) and a per-skill handler hook so deterministic skills don't need an LLM call at all.

**Architecture:** A `Tool` is a small Python callable with declared inputs/outputs and a permission boundary. Tools live under `src/officeplane/content_agent/tools/<name>/tool.py` (one tool per directory, factory function returns a `Tool` instance). Skills can opt into deterministic execution by adding a sibling `handler.py` next to their `SKILL.md`; the handler runs Python directly using tools and returns the output dict. Skills without a handler keep falling back to the LLM-only `litellm.acompletion` path. A future Phase 7b will add a DeepAgents agent loop for skills that need both LLM reasoning and tools (summarize, extract, classify).

**Tech Stack:** Python 3.10+, FastAPI, Prisma + Postgres + pgvector, OpenAI embeddings (existing), LiteLLM, pytest. No new third-party deps required for the deterministic path; the agent-loop path in Phase 7b will leverage existing DeepAgents.

---

## File Structure (target)

```
src/officeplane/
  content_agent/
    skill_executor.py            # extend: dispatch via handler.py if present
    tools/
      __init__.py
      registry.py                # Tool dataclass + register/get/list
      db_query/tool.py           # safe Prisma reads
      db_write/tool.py           # Prisma writes (gated)
      vector_search/tool.py      # pgvector cosine sim on Chunk
      embed_text/tool.py         # OpenAI text-embedding-3-small wrapper
      file_render/tool.py        # docx/pdf/pptx render hook
    skills/
      audit-query/
        SKILL.md                 # already exists
        handler.py               # NEW — deterministic, uses db_query
      document-search/
        SKILL.md                 # already exists
        handler.py               # NEW — deterministic, uses vector_search + db_query
prisma/
  schema.prisma                  # +SKILL_INVOKED EventType
  migrations/<ts>_add_skill_invoked_event_type/migration.sql
tests/
  agent/
    test_tool_registry.py
    test_tool_db_query.py
    test_tool_vector_search.py
    test_skill_handler_audit_query.py
    test_skill_handler_document_search.py
```

---

## Phase 7 — Implementation

### Task 7.1: Tool framework

**Files:**
- Create: `src/officeplane/content_agent/tools/__init__.py` (empty)
- Create: `src/officeplane/content_agent/tools/registry.py`
- Create: `tests/agent/test_tool_registry.py`

- [ ] **Step 1: Write failing test**

```python
"""Tool registry tests (Phase 7.1)."""
from __future__ import annotations

import pytest

from officeplane.content_agent.tools.registry import (
    Tool,
    ToolNotFoundError,
    register_tool,
    get_tool,
    list_tools,
    _reset_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    _reset_for_tests()


def test_register_and_get():
    async def _impl(**kw):
        return {"echo": kw}

    t = Tool(name="echo", description="Echoes inputs", impl=_impl)
    register_tool(t)
    assert get_tool("echo") is t
    assert "echo" in [t.name for t in list_tools()]


def test_get_unknown_raises():
    with pytest.raises(ToolNotFoundError):
        get_tool("nope")


def test_register_duplicate_replaces_silently_with_log():
    async def _a(**kw):
        return {"a": True}

    async def _b(**kw):
        return {"b": True}

    register_tool(Tool(name="dupe", description="", impl=_a))
    register_tool(Tool(name="dupe", description="", impl=_b))
    # Last write wins — supports hot-reload during tests
    assert get_tool("dupe").impl is _b
```

- [ ] **Step 2: Run, expect FAIL**

```bash
docker cp /Users/regina/Desktop/AgenticDocs/AgenticDocs/tests/agent officeplane-api:/app/tests/agent
docker exec --user root officeplane-api chown -R appuser:appuser /app/tests/agent
docker compose exec -T api pytest tests/agent/test_tool_registry.py -v
```

- [ ] **Step 3: Implement `registry.py`**

```python
"""Tool registry: register/lookup tools by name."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

log = logging.getLogger("officeplane.content_agent.tools.registry")


class ToolNotFoundError(KeyError):
    pass


@dataclass
class Tool:
    name: str
    description: str
    impl: Callable[..., Awaitable[dict[str, Any]]]
    inputs: list[dict] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)


_REGISTRY: dict[str, Tool] = {}


def register_tool(tool: Tool) -> None:
    if tool.name in _REGISTRY:
        log.info("re-registering tool %s", tool.name)
    _REGISTRY[tool.name] = tool


def get_tool(name: str) -> Tool:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise ToolNotFoundError(name) from exc


def list_tools() -> list[Tool]:
    return list(_REGISTRY.values())


def _reset_for_tests() -> None:
    _REGISTRY.clear()
```

- [ ] **Step 4: Run, expect PASS**

```bash
docker compose exec -T api pytest tests/agent/test_tool_registry.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/tools tests/agent/test_tool_registry.py
git commit -m "feat(tools): tool registry framework"
```

### Task 7.2: `db_query` tool — safe Prisma reads

**Files:**
- Create: `src/officeplane/content_agent/tools/db_query/__init__.py` (empty)
- Create: `src/officeplane/content_agent/tools/db_query/tool.py`
- Create: `tests/agent/test_tool_db_query.py`

The tool runs a parameterized read against an **allow-listed** set of tables. No raw SQL. Filters are validated against a per-table allow-list of column names to prevent injection through filter keys.

- [ ] **Step 1: Allow-list design**

The allow-list lives at the top of `tool.py`:
```python
_TABLE_ACCESS = {
    "documents":            {"id", "title", "author", "createdAt", "updatedAt", "summary", "topics"},
    "chapters":             {"id", "documentId", "title", "orderIndex", "summary"},
    "sections":             {"id", "chapterId", "title", "orderIndex", "summary"},
    "pages":                {"id", "sectionId", "pageNumber", "wordCount"},
    "executionhistory":     {"id", "eventType", "documentId", "instanceId", "taskId", "actorType", "actorId", "timestamp"},
    "documentinstances":    {"id", "documentId", "state", "driverType", "createdAt"},
    "task_queue":           {"id", "taskType", "state", "documentId", "createdAt"},
}
```

Any table or filter key not in the map → `ValueError`.

- [ ] **Step 2: Write failing test**

```python
"""Tests for db_query tool (Phase 7.2)."""
from __future__ import annotations

import pytest
from prisma import Prisma

from officeplane.content_agent.tools.db_query.tool import db_query


@pytest.mark.asyncio
async def test_query_documents_by_title(seed_one_document):
    rows = await db_query(table="documents", filters={"title": seed_one_document.title}, limit=10)
    assert any(r["id"] == seed_one_document.id for r in rows)


@pytest.mark.asyncio
async def test_query_unknown_table_rejected():
    with pytest.raises(ValueError, match="not allowed"):
        await db_query(table="users", filters={}, limit=10)


@pytest.mark.asyncio
async def test_query_unknown_filter_field_rejected():
    with pytest.raises(ValueError, match="filter"):
        await db_query(table="documents", filters={"DROP TABLE": "hack"}, limit=1)


@pytest.fixture
async def seed_one_document():
    db = Prisma()
    await db.connect()
    try:
        d = await db.document.create(data={"title": f"phase7-test-{__name__}"})
        yield d
        await db.document.delete(where={"id": d.id})
    finally:
        await db.disconnect()
```

- [ ] **Step 3: Run, expect FAIL**

```bash
docker compose exec -T api pytest tests/agent/test_tool_db_query.py -v
```

- [ ] **Step 4: Implement `tool.py`**

```python
"""db_query tool — safe Prisma reads with table/field allow-list."""
from __future__ import annotations

from typing import Any

from prisma import Prisma

from officeplane.content_agent.tools.registry import Tool, register_tool


_TABLE_ACCESS: dict[str, set[str]] = {
    "documents":         {"id", "title", "author", "createdAt", "updatedAt", "summary", "topics"},
    "chapters":          {"id", "documentId", "title", "orderIndex", "summary"},
    "sections":          {"id", "chapterId", "title", "orderIndex", "summary"},
    "pages":             {"id", "sectionId", "pageNumber", "wordCount"},
    "executionhistory":  {"id", "eventType", "documentId", "instanceId", "taskId", "actorType", "actorId", "timestamp"},
    "documentinstances": {"id", "documentId", "state", "driverType", "createdAt"},
    "task_queue":        {"id", "taskType", "state", "documentId", "createdAt"},
}

_TABLE_TO_DELEGATE = {
    "documents": "document",
    "chapters": "chapter",
    "sections": "section",
    "pages": "page",
    "executionhistory": "executionhistory",
    "documentinstances": "documentinstance",
    "task_queue": "task",
}


async def db_query(
    *,
    table: str,
    filters: dict[str, Any] | None = None,
    limit: int = 50,
    order_by: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    if table not in _TABLE_ACCESS:
        raise ValueError(f"table {table!r} not allowed by db_query")
    allowed = _TABLE_ACCESS[table]
    filters = filters or {}
    bad = [k for k in filters if k not in allowed]
    if bad:
        raise ValueError(f"filter field(s) {bad} not allowed for {table}")

    db = Prisma()
    await db.connect()
    try:
        delegate = getattr(db, _TABLE_TO_DELEGATE[table])
        kwargs: dict[str, Any] = {"take": min(limit, 500)}
        if filters:
            kwargs["where"] = filters
        if order_by:
            kwargs["order"] = order_by
        rows = await delegate.find_many(**kwargs)
        return [r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in rows]
    finally:
        await db.disconnect()


def get_tool() -> Tool:
    return Tool(
        name="db_query",
        description="Read rows from an allow-listed Prisma table.",
        impl=lambda **kw: db_query(**kw),
        inputs=[
            {"name": "table", "type": "string", "required": True},
            {"name": "filters", "type": "object", "required": False},
            {"name": "limit", "type": "integer", "required": False},
            {"name": "order_by", "type": "object", "required": False},
        ],
        outputs=[{"name": "rows", "type": "array"}],
    )


# Auto-register on import
register_tool(get_tool())
```

- [ ] **Step 5: Run, expect PASS**

```bash
docker compose exec -T api pytest tests/agent/test_tool_db_query.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/content_agent/tools/db_query tests/agent/test_tool_db_query.py
git commit -m "feat(tools): db_query with allow-listed table/field reads"
```

### Task 7.3: `vector_search` tool

**Files:**
- Create: `src/officeplane/content_agent/tools/vector_search/__init__.py` (empty)
- Create: `src/officeplane/content_agent/tools/vector_search/tool.py`
- Create: `tests/agent/test_tool_vector_search.py`

This tool wraps the existing pgvector cosine similarity logic. There's already a `RAGRetriever` in `src/officeplane/documents/`/related — reuse it instead of writing new SQL.

- [ ] **Step 1: Locate existing retriever**

```bash
grep -rn "class RAGRetriever\|def retrieve\|cosine\|<->\|<=>\|<#>" src/officeplane | head -20
```
Capture the import path. The expected location is `src/officeplane/documents/store.py` or a sibling `retrieval.py`.

- [ ] **Step 2: Write failing test**

```python
"""Tests for vector_search tool (Phase 7.3)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from officeplane.content_agent.tools.vector_search.tool import vector_search


@pytest.mark.asyncio
async def test_vector_search_returns_chunks_with_context():
    fake_chunk = {
        "id": "chunk-1",
        "documentId": "doc-1",
        "chapterId": "chap-1",
        "sectionId": "sec-1",
        "text": "Agentic ECM defines …",
        "score": 0.91,
    }
    with patch(
        "officeplane.content_agent.tools.vector_search.tool._search_chunks",
        new=AsyncMock(return_value=[fake_chunk]),
    ):
        with patch(
            "officeplane.content_agent.tools.vector_search.tool._enrich_with_context",
            new=AsyncMock(side_effect=lambda chunks: chunks),
        ):
            results = await vector_search(query="agentic ECM", top_k=5)
    assert len(results) == 1
    assert results[0]["text"].startswith("Agentic ECM")
```

- [ ] **Step 3: Run, expect FAIL**

- [ ] **Step 4: Implement `tool.py`**

```python
"""vector_search tool — pgvector cosine similarity over Chunk embeddings."""
from __future__ import annotations

from typing import Any

from officeplane.content_agent.tools.registry import Tool, register_tool


async def _embed(query: str) -> list[float]:
    """Produce a 1536-dim embedding via OpenAI text-embedding-3-small."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    resp = await client.embeddings.create(model="text-embedding-3-small", input=query)
    return resp.data[0].embedding


async def _search_chunks(embedding: list[float], top_k: int, collection_id: str | None) -> list[dict[str, Any]]:
    """Run cosine similarity directly via Prisma + raw SQL (pgvector)."""
    from prisma import Prisma

    sql = (
        "SELECT id, document_id, chapter_id, section_id, page_id, text, "
        "1 - (embedding <=> $1::vector) AS score "
        "FROM chunks "
        "ORDER BY embedding <=> $1::vector "
        "LIMIT $2"
    )
    db = Prisma()
    await db.connect()
    try:
        rows = await db.query_raw(sql, embedding, top_k)
    finally:
        await db.disconnect()
    return [
        {
            "id": str(r["id"]),
            "documentId": str(r["document_id"]),
            "chapterId": str(r["chapter_id"]),
            "sectionId": str(r["section_id"]),
            "pageId": str(r["page_id"]),
            "text": r["text"],
            "score": float(r["score"]),
        }
        for r in rows
    ]


async def _enrich_with_context(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add document/chapter/section titles to each chunk."""
    if not chunks:
        return chunks
    from prisma import Prisma

    db = Prisma()
    await db.connect()
    try:
        for ch in chunks:
            doc = await db.document.find_unique(where={"id": ch["documentId"]})
            chap = await db.chapter.find_unique(where={"id": ch["chapterId"]})
            sec = await db.section.find_unique(where={"id": ch["sectionId"]})
            ch["documentTitle"] = doc.title if doc else None
            ch["chapterTitle"] = chap.title if chap else None
            ch["sectionTitle"] = sec.title if sec else None
    finally:
        await db.disconnect()
    return chunks


async def vector_search(
    *,
    query: str,
    top_k: int = 8,
    collection_id: str | None = None,
) -> list[dict[str, Any]]:
    embedding = await _embed(query)
    chunks = await _search_chunks(embedding, top_k=top_k, collection_id=collection_id)
    return await _enrich_with_context(chunks)


def get_tool() -> Tool:
    return Tool(
        name="vector_search",
        description="Cosine similarity search over Chunk embeddings, enriched with document/chapter/section titles.",
        impl=lambda **kw: vector_search(**kw),
        inputs=[
            {"name": "query", "type": "string", "required": True},
            {"name": "top_k", "type": "integer", "required": False},
            {"name": "collection_id", "type": "string", "required": False},
        ],
        outputs=[{"name": "results", "type": "array"}],
    )


register_tool(get_tool())
```

- [ ] **Step 5: Run, expect PASS**

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/content_agent/tools/vector_search tests/agent/test_tool_vector_search.py
git commit -m "feat(tools): vector_search wraps pgvector cosine + hierarchical context"
```

### Task 7.4: Add `SKILL_INVOKED` to EventType enum

**Files:**
- Modify: `prisma/schema.prisma`
- Modify: `src/officeplane/content_agent/skill_executor.py` (replace the `SYSTEM_STARTUP` placeholder)

- [ ] **Step 1: Add enum value**

In `schema.prisma`, the `EventType` enum (around line 247), add `SKILL_INVOKED` next to the other agent-emitted values. Keep alphabetical or grouped — pick one.

- [ ] **Step 2: Migrate**

```bash
docker compose exec -T api npx prisma migrate dev --name add_skill_invoked_event_type
docker compose exec -T api npx prisma generate
```

- [ ] **Step 3: Replace placeholder in `skill_executor.py`**

Find the `_emit_audit` method. Change `"eventType": "SYSTEM_STARTUP"` to `"eventType": "SKILL_INVOKED"` and remove the `# TODO Phase 6` comment.

- [ ] **Step 4: Smoke test**

```bash
docker compose exec -T api python -c "
import asyncio
from officeplane.content_agent.skill_executor import SkillExecutor
from unittest.mock import AsyncMock, MagicMock, patch

async def main():
    ex = SkillExecutor()
    fake = MagicMock(); fake.choices = [MagicMock(message=MagicMock(content='{\"events\": []}'))]
    with patch('officeplane.content_agent.skill_executor.litellm.acompletion', new=AsyncMock(return_value=fake)):
        out = await ex.invoke('audit-query', {'filters': {}})
    print('output:', out)

asyncio.run(main())
"
```
Expected: prints `output: {'events': []}` and a row appears in `execution_history` with `event_type = SKILL_INVOKED`.

- [ ] **Step 5: Commit**

```bash
git add prisma src/officeplane/content_agent/skill_executor.py
git commit -m "feat(audit): add SKILL_INVOKED event type for skill execution"
```

### Task 7.5: SkillExecutor dispatches to handler.py if present

**Files:**
- Modify: `src/officeplane/content_agent/skill_executor.py`
- Create: `tests/agent/test_skill_executor_handler.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for handler-based skill dispatch (Phase 7.5)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from officeplane.content_agent.skill_executor import SkillExecutor


SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src/officeplane/content_agent/skills"


@pytest.mark.asyncio
async def test_handler_path_used_when_present(tmp_path):
    """If skills/<name>/handler.py exists with `async def execute`, invoke calls it
    instead of LiteLLM."""
    skill_dir = tmp_path / "echo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: echo-skill\ndescription: echoes\ninputs: []\noutputs: []\ntools: []\n---\n# echo-skill\n"
    )
    (skill_dir / "handler.py").write_text(
        "async def execute(*, inputs, **kwargs):\n    return {'echoed': inputs}\n"
    )

    ex = SkillExecutor(skills_root=tmp_path)
    with patch("officeplane.content_agent.skill_executor.SkillExecutor._emit_audit", new=AsyncMock()):
        with patch("officeplane.content_agent.skill_executor.litellm.acompletion") as litellm_mock:
            out = await ex.invoke("echo-skill", {"a": 1})
            litellm_mock.assert_not_called()
    assert out == {"echoed": {"a": 1}}


@pytest.mark.asyncio
async def test_no_handler_falls_back_to_litellm(tmp_path):
    skill_dir = tmp_path / "llm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: llm-skill\ndescription: llm only\ninputs: []\noutputs: []\ntools: []\n---\n# llm-skill\n"
    )

    ex = SkillExecutor(skills_root=tmp_path)
    from unittest.mock import MagicMock

    fake = MagicMock(); fake.choices = [MagicMock(message=MagicMock(content='{"x": 1}'))]
    with patch("officeplane.content_agent.skill_executor.SkillExecutor._emit_audit", new=AsyncMock()):
        with patch("officeplane.content_agent.skill_executor.litellm.acompletion", new=AsyncMock(return_value=fake)):
            out = await ex.invoke("llm-skill", {})
    assert out == {"x": 1}
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Modify `invoke()` in `skill_executor.py`**

Add a handler discovery + dispatch step before the LiteLLM call:

```python
async def invoke(self, skill_name, inputs, *, actor_id=None, document_id=None):
    skill = self.get_skill(skill_name)
    self.validate_inputs(skill_name, inputs)

    handler = self._load_handler(skill)
    if handler is not None:
        output = await handler(inputs=inputs, actor_id=actor_id, document_id=document_id)
        await self._emit_audit(skill, output, actor_id=actor_id, document_id=document_id)
        return output

    # …existing LiteLLM path unchanged…
```

Add the helper:

```python
def _load_handler(self, skill):
    """Return the `execute` coroutine from skills/<name>/handler.py if present."""
    if skill.path is None:
        return None
    handler_path = skill.path / "handler.py"
    if not handler_path.exists():
        return None
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        f"officeplane.skills.handlers.{skill.name.replace('-', '_')}",
        handler_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "execute", None)
```

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/skill_executor.py tests/agent/test_skill_executor_handler.py
git commit -m "feat(agent): dispatch via handler.py when present, else LiteLLM"
```

### Task 7.6: Implement `audit-query` handler (real DB)

**Files:**
- Create: `src/officeplane/content_agent/skills/audit-query/handler.py`
- Create: `tests/agent/test_skill_handler_audit_query.py`

- [ ] **Step 1: Write failing test**

```python
"""End-to-end test: audit-query handler returns real ExecutionHistory rows."""
from __future__ import annotations

import pytest
from prisma import Prisma

from officeplane.content_agent.skill_executor import SkillExecutor


@pytest.mark.asyncio
async def test_audit_query_returns_real_events(seed_audit_event):
    ex = SkillExecutor()
    output = await ex.invoke(
        "audit-query",
        {"filters": {"event_type": "DOCUMENT_IMPORTED"}},
    )
    assert "events" in output
    assert any(e["id"] == seed_audit_event.id for e in output["events"])


@pytest.fixture
async def seed_audit_event():
    db = Prisma()
    await db.connect()
    try:
        ev = await db.executionhistory.create(
            data={
                "eventType": "DOCUMENT_IMPORTED",
                "eventMessage": "phase7 fixture",
                "actorType": "test",
            }
        )
        yield ev
        await db.executionhistory.delete(where={"id": ev.id})
    finally:
        await db.disconnect()
```

- [ ] **Step 2: Run, expect FAIL** (handler doesn't exist yet)

- [ ] **Step 3: Implement `handler.py`**

```python
"""Deterministic handler for the audit-query skill."""
from __future__ import annotations

from typing import Any

from officeplane.content_agent.tools.db_query.tool import db_query


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    raw_filters = inputs.get("filters", {}) or {}
    db_filters: dict[str, Any] = {}
    if "event_type" in raw_filters:
        db_filters["eventType"] = raw_filters["event_type"]
    if "document_id" in raw_filters:
        db_filters["documentId"] = raw_filters["document_id"]
    if "actor_id" in raw_filters:
        db_filters["actorId"] = raw_filters["actor_id"]

    rows = await db_query(
        table="executionhistory",
        filters=db_filters,
        limit=int(inputs.get("limit", 100)),
        order_by={"timestamp": "desc"},
    )
    return {"events": rows, "count": len(rows)}
```

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Smoke against the live API**

```bash
curl -s -X POST http://localhost:8001/api/jobs/invoke/audit-query \
  -H "Content-Type: application/json" \
  -d '{"inputs":{"filters":{"event_type":"DOCUMENT_IMPORTED"}}}' | python3 -m json.tool
```
Expected: real events from `execution_history`, NO hallucinated "Annual Report 2024".

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/content_agent/skills/audit-query/handler.py \
        tests/agent/test_skill_handler_audit_query.py
git commit -m "feat(skill): audit-query handler queries ExecutionHistory directly"
```

### Task 7.7: Implement `document-search` handler (real vector search)

**Files:**
- Create: `src/officeplane/content_agent/skills/document-search/handler.py`
- Create: `tests/agent/test_skill_handler_document_search.py`

- [ ] **Step 1: Write failing test**

```python
"""End-to-end test: document-search handler returns real chunks."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from officeplane.content_agent.skill_executor import SkillExecutor


@pytest.mark.asyncio
async def test_document_search_uses_vector_search_tool():
    ex = SkillExecutor()
    fake_chunks = [
        {
            "id": "c1",
            "documentId": "d1",
            "documentTitle": "Real Doc",
            "chapterTitle": "Real Chapter",
            "sectionTitle": "Real Section",
            "text": "Real content text snippet",
            "score": 0.93,
        }
    ]
    with patch(
        "officeplane.content_agent.skills.document_search_handler.vector_search",
        new=AsyncMock(return_value=fake_chunks),
    ):
        output = await ex.invoke("document-search", {"query": "anything", "top_k": 1})

    assert output["results"][0]["document_title"] == "Real Doc"
    assert output["results"][0]["score"] == pytest.approx(0.93)
```

(Note the patch path — handlers loaded by `importlib` get an injected module name. We'll set up a stable import alias in step 3.)

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement `handler.py`**

```python
"""Deterministic handler for document-search."""
from __future__ import annotations

from typing import Any

from officeplane.content_agent.tools.vector_search.tool import vector_search


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    chunks = await vector_search(
        query=inputs["query"],
        top_k=int(inputs.get("top_k", 8)),
        collection_id=inputs.get("collection_id"),
    )
    return {
        "results": [
            {
                "chunk_id": c["id"],
                "document_id": c["documentId"],
                "document_title": c.get("documentTitle"),
                "chapter_title": c.get("chapterTitle"),
                "section_title": c.get("sectionTitle"),
                "score": c["score"],
                "snippet": c["text"][:240],
            }
            for c in chunks
        ]
    }
```

The handler imports `vector_search` directly. The test patch path needs to match — adjust per the importlib-loaded module name. If the test fails to patch correctly, switch to patching the underlying `_search_chunks` and `_enrich_with_context` shown in 7.3.

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: Live smoke**

```bash
curl -s -X POST http://localhost:8001/api/jobs/invoke/document-search \
  -H "Content-Type: application/json" \
  -d '{"inputs":{"query":"agentic","top_k":3}}' | python3 -m json.tool
```
Expected: real chunks from the indexed document store. With an empty store, returns `{"results": []}` — the LLM hallucination is gone.

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/content_agent/skills/document-search/handler.py \
        tests/agent/test_skill_handler_document_search.py
git commit -m "feat(skill): document-search handler runs real pgvector search"
```

### Task 7.8: Wider regression + commit checkpoint

- [ ] **Step 1: Full test run**

```bash
docker compose exec -T api pytest tests/ -q --tb=line --ignore=tests/test_render_real_pptx.py
```

Expected: previous 319 + ~12 new = ~331 passed.

- [ ] **Step 2: Tag the milestone**

```bash
git tag -a phase-7-tools -m "Phase 7: tool layer + first two real-data skills (audit-query, document-search)"
```

- [ ] **Step 3: Push**

```bash
git push origin feat/agentic-ecm-pivot --tags
```

---

## Out of scope for this plan

- Full DeepAgents agent loop with tools (the LLM-needs-tools pattern for `document-summarize`, `document-extract`, `document-classify`, `document-redact`, `document-relate`). That's **Phase 7b** — the executor learns to spawn a DeepAgents instance with the tool registry exposed.
- `db_write`, `file_render`, `embed_text` as standalone tools (only `db_query` and `vector_search` here, both read-only). Write tools land in Phase 7c with proper permission gates.
- `document-export` real implementation (wraps existing render code; needs its own task).
- Migrating the legacy `generate-pptx`/`generate-docx`/`team` skills off the registry. Still parallel-running.
- Multi-tenancy / collection scoping in `db_query`. Add `collection_id` filter once collections are real.
