# Agentic ECM Pivot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot OfficePlane from a half-formed multi-package agent project into a focused open-source agentic ECM: one DeepAgents+LangGraph runtime, filesystem `SKILL.md` capabilities, multi-level document summaries for top-down navigation, LiteLLM for model agnosticism, and 12 ECM-native skills as the product surface.

**Architecture:** A single in-process agent runtime (`src/officeplane/agent/`) executes ECM operations as filesystem-defined skills. The doc store (`Document → Chapter → Section → Page → Chunk`) gains summaries at every level so the agent reads top-down before fetching detail. LiteLLM abstracts the model provider. Existing FastAPI routes either remain as thin agent invocations or as direct CRUD where the user just wants to dump files. MCP is outbound-only for now; an inbound MCP wrapper is a later phase.

**Tech Stack:** Python 3.10+, FastAPI, Prisma + PostgreSQL/pgvector, DeepAgents, LangGraph, LiteLLM, Pydantic Settings, pytest. Frontend remains Next.js + the existing AgenticChat component.

---

## File Structure (target end state)

```
src/officeplane/
  agent/                      # canonical runtime (renamed from content_agent/)
    __init__.py
    runner.py                 # build_agent(), invoke_agent()
    model.py                  # LiteLLM-backed model factory
    skill_loader.py           # discovers skills/<name>/SKILL.md
    tool_loader.py            # discovers tools/<name>/tool.py
    config.py                 # Pydantic Settings
    prompts.py                # system prompt template
    streaming.py              # (kept from content_agent/)
    storage.py                # (kept)
    workspace.py              # (kept)
  agent/skills/               # filesystem skill catalog
    document-ingest/SKILL.md
    document-search/SKILL.md
    document-classify/SKILL.md
    document-summarize/SKILL.md
    document-extract/SKILL.md
    document-version/SKILL.md
    document-redact/SKILL.md
    document-relate/SKILL.md
    document-export/SKILL.md
    document-workflow/SKILL.md
    collection-manage/SKILL.md
    audit-query/SKILL.md
  agent/tools/                # LangChain BaseTool factories
    db-query/tool.py
    vector-search/tool.py
    file-render/tool.py
  api/                        # unchanged surface, internals rewired
  ingestion/                  # unchanged + summary-emit
  documents/                  # unchanged + summary persistence
  ecm/                        # unchanged
  storage/                    # unchanged
  management/                 # unchanged
DELETED:
  agentic/                    # workchestrator — gone
  agent_team/                 # multi-agent — deferred
  skills/                     # Python skill base — replaced by filesystem
  content_agent/              # renamed to agent/
prisma/
  schema.prisma               # +Document.summary/topics, +Section.summary, etc.
  migrations/                 # new migration for summary cols
```

---

## Phase 1 — Multi-Level Document Summaries

**Why first:** Every later phase (skills that traverse docs, top-down generation) needs summary fields to exist. Pure additive schema change.

### Task 1.1: Add summary fields to Prisma schema

**Files:**
- Modify: `prisma/schema.prisma`

- [ ] **Step 1: Edit `Document` model — add summary, topics, keyEntities**

In `prisma/schema.prisma`, in the `Document` model block, add the following fields after `fileName`:

```prisma
  summary       String?  @db.Text
  topics        String[] @default([])
  keyEntities   Json     @default("{}") @map("key_entities")
  summaryModel  String?  @map("summary_model")
  summarizedAt  DateTime? @map("summarized_at") @db.Timestamptz
```

- [ ] **Step 2: Edit `Section` model — add summary**

In the `Section` model block, after `orderIndex`, add:

```prisma
  summary    String?  @db.Text
```

(`Chapter.summary` already exists — verify line 53 of schema.prisma; do not duplicate.)

- [ ] **Step 3: Generate Prisma migration**

Run:
```bash
docker compose exec -T api npx prisma migrate dev --name add_document_summaries --create-only
```
Expected: a new file under `prisma/migrations/<timestamp>_add_document_summaries/migration.sql` with `ALTER TABLE` statements adding the columns.

- [ ] **Step 4: Inspect the generated SQL**

Open the generated `migration.sql` and confirm it contains exactly:
- `ALTER TABLE "documents" ADD COLUMN "summary" TEXT, ADD COLUMN "topics" TEXT[] ...`
- `ALTER TABLE "sections" ADD COLUMN "summary" TEXT`

If anything else changed (renames, drops), abort and investigate.

- [ ] **Step 5: Apply migration**

Run:
```bash
docker compose exec -T api npx prisma migrate deploy
docker compose exec -T api npx prisma generate
```
Expected: "All migrations have been successfully applied."

- [ ] **Step 6: Commit**

```bash
git add prisma/schema.prisma prisma/migrations
git commit -m "feat(db): add multi-level document summary fields"
```

### Task 1.2: Test summary persistence round-trip

**Files:**
- Create: `tests/db/test_document_summaries.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from prisma import Prisma

@pytest.mark.asyncio
async def test_document_summary_round_trip():
    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.create(
            data={
                "title": "Summary Test",
                "summary": "Top-level overview.",
                "topics": ["ai", "ethics"],
                "keyEntities": {"people": ["Alice"], "orgs": ["Acme"]},
            }
        )
        assert doc.summary == "Top-level overview."
        assert doc.topics == ["ai", "ethics"]
        assert doc.keyEntities["people"] == ["Alice"]

        sec_doc = await db.document.create(data={"title": "Sec parent"})
        chap = await db.chapter.create(
            data={"documentId": sec_doc.id, "title": "C1", "orderIndex": 0, "summary": "chap summary"}
        )
        sec = await db.section.create(
            data={"chapterId": chap.id, "title": "S1", "orderIndex": 0, "summary": "sec summary"}
        )
        assert sec.summary == "sec summary"
    finally:
        await db.disconnect()
```

- [ ] **Step 2: Run test, expect PASS**

```bash
docker compose exec -T api pytest tests/db/test_document_summaries.py -v
```
Expected: PASS. Failure here means the migration didn't apply — re-run Step 5 of Task 1.1.

- [ ] **Step 3: Commit**

```bash
git add tests/db/test_document_summaries.py
git commit -m "test(db): cover document/section/chapter summary fields"
```

### Task 1.3: Emit summaries from the ingestion pipeline

**Files:**
- Modify: `src/officeplane/ingestion/prompts.py`
- Modify: `src/officeplane/ingestion/structure_parser.py`
- Modify: `src/officeplane/ingestion/ingestion_service.py`
- Test: `tests/ingestion/test_summary_emission.py`

- [ ] **Step 1: Update vision prompt to request summary**

Edit `prompts.py` — find the structure-extraction prompt and append:

```python
SUMMARY_INSTRUCTION = """
After extracting structure, emit a JSON field `document_summary` (3-5 sentence overview),
a `topics` array (3-8 short tags), and a `key_entities` object with optional keys:
people, orgs, places, dates. For each chapter and section, emit a `summary` field
(1-3 sentences). Return all summaries as plain text, no markdown.
"""
```

Append `SUMMARY_INSTRUCTION` to the existing structure prompt template.

- [ ] **Step 2: Write failing parser test**

Create `tests/ingestion/test_summary_emission.py`:

```python
from officeplane.ingestion.structure_parser import parse_structure

def test_parser_extracts_document_summary():
    raw = {
        "document_summary": "An overview.",
        "topics": ["x", "y"],
        "key_entities": {"people": ["A"]},
        "chapters": [
            {"title": "C", "order": 0, "summary": "chap sum",
             "sections": [{"title": "S", "order": 0, "summary": "sec sum", "pages": []}]}
        ],
    }
    parsed = parse_structure(raw)
    assert parsed.summary == "An overview."
    assert parsed.topics == ["x", "y"]
    assert parsed.chapters[0].summary == "chap sum"
    assert parsed.chapters[0].sections[0].summary == "sec sum"
```

- [ ] **Step 3: Run, expect FAIL**

```bash
docker compose exec -T api pytest tests/ingestion/test_summary_emission.py -v
```
Expected: FAIL — `parse_structure` doesn't read summary fields yet.

- [ ] **Step 4: Update parser**

In `structure_parser.py`, find the dataclass / Pydantic model for the parsed document. Add fields `summary: str | None`, `topics: list[str]`, `key_entities: dict`. Add `summary: str | None` to chapter and section models. Update the parsing logic to copy these from the raw dict.

- [ ] **Step 5: Run test, expect PASS**

```bash
docker compose exec -T api pytest tests/ingestion/test_summary_emission.py -v
```

- [ ] **Step 6: Persist summaries in ingestion_service**

In `ingestion_service.py`, find where the parsed structure is written to the DB. Update the `db.document.create(data=...)` call to include `summary`, `topics`, `keyEntities`, `summaryModel` (set from config), `summarizedAt` (now). Update chapter/section creates to include `summary`.

- [ ] **Step 7: Add integration test**

Append to `tests/ingestion/test_summary_emission.py`:

```python
import pytest
from officeplane.ingestion.ingestion_service import IngestionService
from officeplane.ingestion.vision_adapters.mock import MockVisionAdapter

@pytest.mark.asyncio
async def test_ingestion_persists_summary(tmp_path):
    adapter = MockVisionAdapter(canned_summary="Mocked overview.", canned_topics=["t1"])
    svc = IngestionService(vision=adapter)
    doc_id = await svc.ingest_pdf_bytes(b"%PDF-fake", filename="x.pdf")
    from prisma import Prisma
    db = Prisma(); await db.connect()
    try:
        d = await db.document.find_unique(where={"id": doc_id})
        assert d.summary == "Mocked overview."
        assert "t1" in d.topics
    finally:
        await db.disconnect()
```

If `MockVisionAdapter` doesn't accept canned summary args yet, add them in `vision_adapters/mock.py`.

- [ ] **Step 8: Run, expect PASS**

```bash
docker compose exec -T api pytest tests/ingestion/test_summary_emission.py -v
```

- [ ] **Step 9: Commit**

```bash
git add src/officeplane/ingestion tests/ingestion/test_summary_emission.py
git commit -m "feat(ingestion): emit and persist multi-level summaries"
```

---

## Phase 2 — LiteLLM Model Layer

**Why:** Sibling repos use a per-provider model factory (OpenAI / Gemini / Bedrock). LiteLLM collapses that to one SDK with provider-prefixed model strings (`openai/gpt-4o`, `gemini/gemini-2.5-pro`, `anthropic/claude-opus-4-7`). Future provider swaps = config change.

### Task 2.1: Add LiteLLM dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add to `agent` optional-deps block**

In `pyproject.toml`, locate the `[project.optional-dependencies]` `agent = [ ... ]` array (currently has langgraph, deepagents, langchain-openai). Add:

```toml
  "litellm>=1.50.0",
  "langchain-litellm>=0.1.0",
```

- [ ] **Step 2: Rebuild the API container**

```bash
docker compose build api
docker compose up -d api
```

- [ ] **Step 3: Verify import**

```bash
docker compose exec -T api python -c "import litellm, langchain_litellm; print(litellm.__version__)"
```
Expected: a version string prints.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): add litellm and langchain-litellm"
```

### Task 2.2: Create the model factory

**Files:**
- Create: `src/officeplane/agent/model.py` (note: `agent/` is created by Phase 3; for now write to `content_agent/model.py` and move it in Phase 3 — adjust the import paths there)
- Create: `tests/agent/test_model_factory.py`

> Decision: write the file at `content_agent/model.py` now and move with the rest of the package in Phase 3. Avoids a half-renamed tree mid-plan.

- [ ] **Step 1: Write failing test**

Create `tests/agent/test_model_factory.py`:

```python
import pytest
from officeplane.content_agent.model import build_chat_model, ModelConfig

def test_build_model_with_openai_string():
    cfg = ModelConfig(model="openai/gpt-4o-mini", temperature=0.0)
    m = build_chat_model(cfg)
    assert m is not None
    assert "gpt-4o-mini" in repr(m).lower() or "gpt-4o-mini" in m.model

def test_build_model_with_gemini_string():
    cfg = ModelConfig(model="gemini/gemini-2.5-pro")
    m = build_chat_model(cfg)
    assert m is not None

def test_build_model_rejects_empty():
    with pytest.raises(ValueError):
        build_chat_model(ModelConfig(model=""))
```

- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError`)

```bash
docker compose exec -T api pytest tests/agent/test_model_factory.py -v
```

- [ ] **Step 3: Implement `model.py`**

Create `src/officeplane/content_agent/model.py`:

```python
from dataclasses import dataclass
from langchain_litellm import ChatLiteLLM


@dataclass
class ModelConfig:
    model: str
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout: int = 120


def build_chat_model(cfg: ModelConfig) -> ChatLiteLLM:
    if not cfg.model:
        raise ValueError("ModelConfig.model is required (e.g. 'openai/gpt-4o-mini')")
    return ChatLiteLLM(
        model=cfg.model,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        request_timeout=cfg.timeout,
    )
```

- [ ] **Step 4: Run, expect PASS**

```bash
docker compose exec -T api pytest tests/agent/test_model_factory.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/model.py tests/agent/test_model_factory.py
git commit -m "feat(agent): add LiteLLM-backed chat model factory"
```

### Task 2.3: Wire runner.py to use the new factory

**Files:**
- Modify: `src/officeplane/content_agent/runner.py`
- Modify: `src/officeplane/content_agent/config.py`

- [ ] **Step 1: Inspect current runner**

Read `src/officeplane/content_agent/runner.py` end-to-end. Identify the call(s) that instantiate the LLM (look for `ChatOpenAI`, `OpenAI(`, or similar). Note the line numbers.

- [ ] **Step 2: Add `model` to settings**

In `config.py`, ensure the Pydantic `Settings` class has:

```python
model: str = Field(default="openai/gpt-4o-mini", alias="OFFICEPLANE_AGENT_MODEL")
temperature: float = Field(default=0.0, alias="OFFICEPLANE_AGENT_TEMPERATURE")
```

- [ ] **Step 3: Replace LLM instantiation in runner.py**

Replace direct provider instantiation with:

```python
from officeplane.content_agent.model import ModelConfig, build_chat_model

def _build_model(settings):
    return build_chat_model(ModelConfig(
        model=settings.model,
        temperature=settings.temperature,
    ))
```

Use `_build_model(settings)` wherever `ChatOpenAI(...)` was called.

- [ ] **Step 4: Run existing agent tests**

```bash
docker compose exec -T api pytest tests/agent -v
```
Expected: PASS. If any test was provider-coupled (`assert isinstance(m, ChatOpenAI)`), update it to assert against `ChatLiteLLM`.

- [ ] **Step 5: Smoke test the runner**

```bash
docker compose exec -T api python -c "
from officeplane.content_agent.config import Settings
from officeplane.content_agent.runner import build_agent
agent = build_agent(Settings())
print(type(agent).__name__)
"
```
Expected: agent type name prints, no exception.

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/content_agent/runner.py src/officeplane/content_agent/config.py
git commit -m "refactor(agent): route runner through LiteLLM factory"
```

---

## Phase 3 — Package Consolidation

**Why:** Four overlapping packages (`agentic/`, `agent_team/`, `content_agent/`, `skills/`) confuse the codebase. Collapse to one canonical `agent/`.

### Task 3.1: Audit usages before deleting

**Files:**
- Read-only inspection.

- [ ] **Step 1: List importers of `agentic`**

```bash
grep -rn "from officeplane.agentic\|import officeplane.agentic" src/ tests/ ui/ 2>/dev/null
```
Record the file:line list. If non-empty, those callers need migration in later steps.

- [ ] **Step 2: List importers of `agent_team`**

```bash
grep -rn "from officeplane.agent_team\|import officeplane.agent_team" src/ tests/ ui/ 2>/dev/null
```

- [ ] **Step 3: List importers of `skills` (the package, not the directory in content_agent)**

```bash
grep -rn "from officeplane.skills\|import officeplane.skills" src/ tests/ ui/ 2>/dev/null
```

- [ ] **Step 4: Save the audit**

Append the three lists to a temp file `/tmp/import-audit.txt`. We'll reference it as we migrate or delete imports.

### Task 3.2: Delete `agentic/`

**Files:**
- Delete: `src/officeplane/agentic/`

- [ ] **Step 1: Migrate any callers**

For each file from Step 1 of Task 3.1: read the file, identify what `agentic.*` was providing. If it's `workchestrator`, replace the call site with a TODO comment and a direct call to `content_agent.runner.invoke_agent(...)`. If you cannot remove a usage cleanly, STOP and ask the operator before deleting.

- [ ] **Step 2: Remove the directory**

```bash
git rm -r src/officeplane/agentic
```

- [ ] **Step 3: Run tests**

```bash
docker compose exec -T api pytest -x
```
Expected: PASS. Fix any import errors.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: remove agentic/ workchestrator (folded into runner)"
```

### Task 3.3: Delete `agent_team/`

**Files:**
- Delete: `src/officeplane/agent_team/`

- [ ] **Step 1: Migrate callers (same pattern as 3.2)**

For each file from Step 2 of Task 3.1: stub out multi-agent calls or remove the feature. Multi-agent is deferred — we want a single deep-agent first.

- [ ] **Step 2: Remove the directory**

```bash
git rm -r src/officeplane/agent_team
```

- [ ] **Step 3: Run tests, then commit**

```bash
docker compose exec -T api pytest -x
git commit -m "refactor: remove agent_team/ (multi-agent deferred)"
```

### Task 3.4: Delete the legacy Python `skills/` package

**Files:**
- Delete: `src/officeplane/skills/`

- [ ] **Step 1: Migrate callers**

For each importer from Step 3 of Task 3.1, replace with a TODO and the future SKILL.md-loader call (`from officeplane.agent.skill_loader import load_skill`). The loader doesn't exist yet — that's fine; tests for those call sites should fail and be marked `@pytest.mark.xfail(reason="skill loader pending Phase 4")` until Phase 4 lands.

- [ ] **Step 2: Remove the directory**

```bash
git rm -r src/officeplane/skills
```

- [ ] **Step 3: Run tests, then commit**

```bash
docker compose exec -T api pytest -x
git commit -m "refactor: remove legacy skills/ package (replaced by SKILL.md filesystem loader)"
```

### Task 3.5: Rename `content_agent/` → `agent/`

**Files:**
- Move: `src/officeplane/content_agent/` → `src/officeplane/agent/`
- Update: every importer.

- [ ] **Step 1: git mv the directory**

```bash
git mv src/officeplane/content_agent src/officeplane/agent
```

- [ ] **Step 2: Update imports across the repo**

```bash
grep -rl "officeplane.content_agent" src/ tests/ ui/ 2>/dev/null | \
  xargs sed -i '' 's/officeplane\.content_agent/officeplane.agent/g'
```

(macOS `sed -i ''`. On Linux drop the `''`.)

- [ ] **Step 3: Verify no stale references**

```bash
grep -rn "content_agent" src/ tests/
```
Expected: empty. If anything remains (string literals, docs), update by hand.

- [ ] **Step 4: Run tests**

```bash
docker compose exec -T api pytest -x
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename content_agent -> agent (canonical runtime)"
```

---

## Phase 4 — Filesystem Skill Loader

**Why:** Replace Python skill classes with `SKILL.md` files (YAML frontmatter + markdown body), matching the sibling repos and the AGENTS.md/SKILL.md open standard. Skills become product spec, not code.

### Task 4.1: Define the SKILL.md schema

**Files:**
- Create: `src/officeplane/agent/skill_loader.py`
- Create: `tests/agent/test_skill_loader.py`
- Create: `src/officeplane/agent/skills/_example/SKILL.md` (fixture skill for tests)

- [ ] **Step 1: Write the example skill**

Create `src/officeplane/agent/skills/_example/SKILL.md`:

```markdown
---
name: _example
description: Test fixture skill — do not invoke in production
inputs:
  - name: query
    type: string
    required: true
outputs:
  - name: result
    type: string
tools: []
---

# Example skill

Body of the skill — guidance for the agent.
```

- [ ] **Step 2: Write failing loader test**

Create `tests/agent/test_skill_loader.py`:

```python
from pathlib import Path
from officeplane.agent.skill_loader import load_skill, discover_skills

SKILLS_ROOT = Path(__file__).parents[2] / "src/officeplane/agent/skills"

def test_load_single_skill():
    s = load_skill(SKILLS_ROOT / "_example")
    assert s.name == "_example"
    assert s.description.startswith("Test fixture")
    assert s.inputs[0].name == "query"
    assert s.body.startswith("# Example skill")

def test_discover_finds_example():
    skills = discover_skills(SKILLS_ROOT)
    names = [s.name for s in skills]
    assert "_example" in names
```

- [ ] **Step 3: Run, expect FAIL**

```bash
docker compose exec -T api pytest tests/agent/test_skill_loader.py -v
```

- [ ] **Step 4: Implement the loader**

Create `src/officeplane/agent/skill_loader.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class SkillInput:
    name: str
    type: str
    required: bool = False
    description: str = ""


@dataclass
class SkillOutput:
    name: str
    type: str
    description: str = ""


@dataclass
class Skill:
    name: str
    description: str
    inputs: list[SkillInput] = field(default_factory=list)
    outputs: list[SkillOutput] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    body: str = ""
    path: Path | None = None


def load_skill(skill_dir: Path) -> Skill:
    md_path = skill_dir / "SKILL.md"
    if not md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")
    raw = md_path.read_text()
    if not raw.startswith("---"):
        raise ValueError(f"{md_path} missing YAML frontmatter")
    _, frontmatter, body = raw.split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}
    return Skill(
        name=meta["name"],
        description=meta.get("description", ""),
        inputs=[SkillInput(**i) for i in meta.get("inputs", [])],
        outputs=[SkillOutput(**o) for o in meta.get("outputs", [])],
        tools=meta.get("tools", []),
        body=body.strip(),
        path=skill_dir,
    )


def discover_skills(root: Path) -> list[Skill]:
    skills = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            skills.append(load_skill(child))
    return skills
```

- [ ] **Step 5: Add `pyyaml` if missing**

```bash
docker compose exec -T api python -c "import yaml; print(yaml.__version__)"
```
If `ModuleNotFoundError`, add `"pyyaml>=6.0"` to `pyproject.toml` core deps and rebuild.

- [ ] **Step 6: Run, expect PASS**

```bash
docker compose exec -T api pytest tests/agent/test_skill_loader.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/officeplane/agent/skill_loader.py src/officeplane/agent/skills/_example tests/agent/test_skill_loader.py
git commit -m "feat(agent): filesystem SKILL.md loader"
```

### Task 4.2: Inject skills into the system prompt

**Files:**
- Modify: `src/officeplane/agent/prompts.py`
- Modify: `src/officeplane/agent/runner.py`
- Test: `tests/agent/test_prompt_assembly.py`

- [ ] **Step 1: Write failing prompt-assembly test**

```python
from officeplane.agent.prompts import build_system_prompt
from officeplane.agent.skill_loader import discover_skills
from pathlib import Path

def test_prompt_includes_skill_descriptions():
    skills = discover_skills(Path("src/officeplane/agent/skills"))
    prompt = build_system_prompt(skills=skills, user_context="")
    assert "_example" in prompt
    assert "Test fixture" in prompt
```

- [ ] **Step 2: Run, expect FAIL**

```bash
docker compose exec -T api pytest tests/agent/test_prompt_assembly.py -v
```

- [ ] **Step 3: Implement `build_system_prompt`**

In `prompts.py`:

```python
from officeplane.agent.skill_loader import Skill

SYSTEM_PROMPT_TEMPLATE = """You are an OfficePlane agent — an agentic enterprise content management runtime.

Available skills:
{skill_index}

Skill detail:
{skill_bodies}

User context:
{user_context}

Rules:
- Read document summaries before fetching pages.
- Use vector search for semantic queries; full-text for exact matches.
- Every mutation must emit an audit event.
"""

def build_system_prompt(*, skills: list[Skill], user_context: str) -> str:
    index = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    bodies = "\n\n".join(f"## {s.name}\n{s.body}" for s in skills)
    return SYSTEM_PROMPT_TEMPLATE.format(
        skill_index=index, skill_bodies=bodies, user_context=user_context,
    )
```

- [ ] **Step 4: Wire `runner.py` to use it**

Replace inline system-prompt strings in `runner.py` with `build_system_prompt(skills=discover_skills(...), user_context=...)`.

- [ ] **Step 5: Run all agent tests, expect PASS**

```bash
docker compose exec -T api pytest tests/agent -v
```

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/agent/prompts.py src/officeplane/agent/runner.py tests/agent/test_prompt_assembly.py
git commit -m "feat(agent): inject SKILL.md content into system prompt"
```

---

## Phase 5 — ECM Skill Catalog (Stubs)

**Why:** Define the product surface. Each skill is a `SKILL.md` describing what the agent does for that ECM verb. Implementation comes later, per skill — but the catalog itself locks the scope.

### Task 5.1: Author 12 SKILL.md stubs

**Files:**
- Create: 12 `src/officeplane/agent/skills/<name>/SKILL.md`

- [ ] **Step 1: Create directories**

```bash
cd src/officeplane/agent/skills
for s in document-ingest document-search document-classify document-summarize \
         document-extract document-version document-redact document-relate \
         document-export document-workflow collection-manage audit-query; do
  mkdir -p "$s"
done
```

- [ ] **Step 2: Write each SKILL.md**

For each of the 12 skills, write `SKILL.md` with frontmatter (name, description, inputs, outputs, tools) and a body that explains in 1-2 paragraphs:
- the ECM verb this skill implements
- when the agent should use it
- which tools it calls
- which DB tables it touches
- audit event(s) it emits

Example for `document-search/SKILL.md`:

```markdown
---
name: document-search
description: Hybrid vector + full-text search across the document store, returning ranked chunks with hierarchical context (document, chapter, section).
inputs:
  - name: query
    type: string
    required: true
  - name: top_k
    type: integer
    required: false
  - name: collection_id
    type: string
    required: false
outputs:
  - name: results
    type: array
    description: List of {chunk_id, document_id, document_title, chapter_title, section_title, score, snippet}
tools:
  - vector-search
  - db-query
---

# document-search

Use this skill when the user asks a semantic question about indexed documents.
Top-down approach: first inspect `Document.summary` and `Document.topics` for candidate docs,
then fetch relevant chunks via pgvector cosine similarity (use the `vector-search` tool),
then enrich with hierarchical context (chapter/section titles) via `db-query`.

If the user provides a `collection_id`, scope the search to that collection's documents.
Emit `DOCUMENT_QUERIED` audit event with the query string and result count.
```

Repeat the same shape for the other 11 skills. Reference the table below for what each one is:

| Skill | One-line scope |
|---|---|
| document-ingest | Upload + vision parse + structure store + summary emission |
| document-search | Hybrid vector + full-text search with hierarchical context |
| document-classify | Apply taxonomy / retention bucket / sensitivity label |
| document-summarize | Generate or refresh document/chapter/section summaries |
| document-extract | Pull structured fields (contracts, invoices, forms) |
| document-version | Create version, diff against prior, rollback |
| document-redact | Strip PII / sensitive entities, store redacted copy |
| document-relate | Create / query relations between documents (graph edges) |
| document-export | Render docx/pdf/pptx/html (wraps existing generators) |
| document-workflow | Approval / sign-off state machine |
| collection-manage | Create folder, move docs, manage ACL inheritance |
| audit-query | Read-only over ExecutionHistory with filters |

- [ ] **Step 3: Verify all 12 load**

```bash
docker compose exec -T api python -c "
from pathlib import Path
from officeplane.agent.skill_loader import discover_skills
ss = discover_skills(Path('src/officeplane/agent/skills'))
names = sorted(s.name for s in ss if s.name != '_example')
print(len(names), names)
assert len(names) == 12, f'expected 12, got {len(names)}'
"
```
Expected: prints `12 [...]`.

- [ ] **Step 4: Commit**

```bash
git add src/officeplane/agent/skills
git commit -m "feat(skills): scaffold 12 ECM skill specs as SKILL.md"
```

### Task 5.2: Runtime test — agent loads catalog

**Files:**
- Test: `tests/agent/test_catalog_loaded.py`

- [ ] **Step 1: Write the test**

```python
from officeplane.agent.runner import build_agent
from officeplane.agent.config import Settings

def test_agent_loads_full_catalog():
    settings = Settings(model="openai/gpt-4o-mini")
    agent = build_agent(settings)
    prompt = agent.system_prompt if hasattr(agent, "system_prompt") else str(agent)
    for skill in [
        "document-ingest", "document-search", "document-classify",
        "document-summarize", "document-extract", "document-version",
        "document-redact", "document-relate", "document-export",
        "document-workflow", "collection-manage", "audit-query",
    ]:
        assert skill in prompt, f"{skill} missing from system prompt"
```

- [ ] **Step 2: Run, expect PASS**

```bash
docker compose exec -T api pytest tests/agent/test_catalog_loaded.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/agent/test_catalog_loaded.py
git commit -m "test(agent): assert full ECM skill catalog reaches system prompt"
```

---

## Phase 6 — Wire Mocked ECM Routes (audit + permissions first)

**Why:** API surfaces lie today — many ECM routes return mock data. Land the two foundational ones (audit, permissions) so every later skill emits real events and respects real ACLs.

### Task 6.1: Real audit log endpoint

**Files:**
- Modify: `src/officeplane/api/` (find the ECM audit route — likely `documents` router)
- Test: `tests/api/test_audit_endpoint.py`

- [ ] **Step 1: Locate the mocked route**

```bash
grep -rn "audit\|ExecutionHistory\|history" src/officeplane/api/
```

- [ ] **Step 2: Write failing test**

```python
import pytest
from httpx import AsyncClient
from officeplane.api.app import app

@pytest.mark.asyncio
async def test_get_audit_returns_real_history(seeded_doc_with_history):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get(f"/api/ecm/documents/{seeded_doc_with_history}/audit")
    assert r.status_code == 200
    body = r.json()
    assert "events" in body
    assert len(body["events"]) > 0
    assert body["events"][0]["eventType"] in ("DOCUMENT_CREATED", "DOCUMENT_IMPORTED")
```

You'll need a `seeded_doc_with_history` fixture in `conftest.py` — create one that inserts a Document and an ExecutionHistory row.

- [ ] **Step 3: Run, expect FAIL**

- [ ] **Step 4: Implement the route**

Replace the mocked handler with a real query:

```python
@router.get("/documents/{document_id}/audit")
async def get_document_audit(document_id: str, limit: int = 100, db: Prisma = Depends(get_db)):
    events = await db.executionhistory.find_many(
        where={"documentId": document_id},
        order={"timestamp": "desc"},
        take=limit,
    )
    return {"events": [e.dict() for e in events]}
```

- [ ] **Step 5: Run, expect PASS**

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(api): wire real audit log query for documents"
```

### Task 6.2: Real permissions read/update

**Files:**
- Modify: `prisma/schema.prisma` (add `DocumentPermission` model if missing)
- Modify: `src/officeplane/api/<documents-router>.py`
- Test: `tests/api/test_permissions.py`

- [ ] **Step 1: Add `DocumentPermission` model to schema**

```prisma
enum PermissionLevel {
  NONE
  READ
  WRITE
  ADMIN
}

model DocumentPermission {
  id           String          @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  documentId   String          @map("document_id") @db.Uuid
  principalId  String          @map("principal_id")
  principalType String         @map("principal_type") // 'user' | 'group'
  level        PermissionLevel
  grantedBy    String?         @map("granted_by")
  grantedAt    DateTime        @default(now()) @map("granted_at") @db.Timestamptz

  document Document @relation(fields: [documentId], references: [id], onDelete: Cascade)

  @@unique([documentId, principalId])
  @@index([documentId])
  @@map("document_permissions")
}
```

Add `permissions DocumentPermission[]` to the `Document` model relations.

- [ ] **Step 2: Migrate**

```bash
docker compose exec -T api npx prisma migrate dev --name add_document_permissions
```

- [ ] **Step 3: Write failing GET test**

Create `tests/api/test_permissions.py`:

```python
import pytest
from httpx import AsyncClient
from officeplane.api.app import app

@pytest.mark.asyncio
async def test_get_permissions_returns_grants(seeded_doc_with_perms):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get(f"/api/ecm/documents/{seeded_doc_with_perms}/permissions")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["permissions"], list)
    assert any(p["level"] == "WRITE" for p in body["permissions"])

@pytest.mark.asyncio
async def test_put_permission_grants(seeded_doc):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.put(
            f"/api/ecm/documents/{seeded_doc}/permissions",
            json={"principalId": "alice", "principalType": "user", "level": "READ"},
        )
    assert r.status_code == 200
    g = await ac.get(f"/api/ecm/documents/{seeded_doc}/permissions")
    assert any(p["principalId"] == "alice" and p["level"] == "READ" for p in g.json()["permissions"])
```

Add `seeded_doc` and `seeded_doc_with_perms` fixtures to `tests/conftest.py` that create the rows in Prisma.

- [ ] **Step 4: Run, expect FAIL**

```bash
docker compose exec -T api pytest tests/api/test_permissions.py -v
```

- [ ] **Step 5: Implement GET handler**

```python
@router.get("/documents/{document_id}/permissions")
async def get_permissions(document_id: str, db: Prisma = Depends(get_db)):
    perms = await db.documentpermission.find_many(where={"documentId": document_id})
    return {"permissions": [p.dict() for p in perms]}
```

- [ ] **Step 6: Implement PUT handler**

```python
class GrantPermissionBody(BaseModel):
    principalId: str
    principalType: str
    level: PermissionLevel

@router.put("/documents/{document_id}/permissions")
async def put_permission(
    document_id: str,
    body: GrantPermissionBody,
    db: Prisma = Depends(get_db),
):
    perm = await db.documentpermission.upsert(
        where={"documentId_principalId": {"documentId": document_id, "principalId": body.principalId}},
        data={
            "create": {
                "documentId": document_id,
                "principalId": body.principalId,
                "principalType": body.principalType,
                "level": body.level,
            },
            "update": {"level": body.level, "principalType": body.principalType},
        },
    )
    await db.executionhistory.create(data={
        "eventType": "DOCUMENT_EDITED",
        "eventMessage": f"Permission granted: {body.principalId} -> {body.level}",
        "documentId": document_id,
    })
    return perm.dict()
```

- [ ] **Step 7: Run, expect PASS**

```bash
docker compose exec -T api pytest tests/api/test_permissions.py -v
```

- [ ] **Step 8: Commit**

```bash
git add prisma tests/api/test_permissions.py src/officeplane/api
git commit -m "feat(api): real RBAC for document permissions with audit emit"
```

### Task 6.3: Defer the rest

Workflows, retention, relations, versioning, subscriptions remain mocked for now. Each gets its own follow-up plan when the corresponding skill lands.

---

## Phase 7 — Inbound MCP (deferred)

Not implemented in this plan. When prioritized, a future plan will add `src/officeplane/mcp_server/` exposing the ECM skills as MCP tools so external agents (Claude Desktop, Cursor, other teams' runners) can use OfficePlane as a content backend. The same skill bodies stay canonical; MCP is a thin translation layer.

---

## Verification

After every phase, run the harness gate:

```bash
./scripts/check-all.sh
```

After Phases 1-5, run:

```bash
docker compose exec -T api pytest -v
```

Expected: all green. If `/dev-loop` is run, the five subagents (arch-guardian, security-auditor, ui-guardian, test-inspector, entropy-sweeper) should accept the changes; if any reject, fix per their feedback before continuing.

---

## Out of scope for this plan

- Multi-tenancy (org/team isolation at DB level) — needs its own design.
- Multi-agent (`agent_team/` revival) — deferred until single-agent is solid.
- Frontend changes — the existing `AgenticChat` already speaks to the runner; no UI work required for this pivot.
- Direct provider SDK removal (`google-generativeai`, `openai`) — keep them; ingestion uses Gemini directly, only the *agent* speaks LiteLLM.
