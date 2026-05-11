# Doc Tree Refactor + Editable Document Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace LMS-flavoured `modules → lessons → blocks` schema with an agnostic recursive `Document → Section → Block` tree aligned to CommonMark/Pandoc/ProseMirror conventions, then add edit (insert / replace / delete) operations, image-block generation via the existing `image-generation` skill, and a parameterised PPTX skill that takes `slide_count`, `style`, `audience`, `tone`.

**Architecture:** Document is a JSON tree. Sections nest to arbitrary depth (`level: 1..N`). Leaves are content blocks aligned to CommonMark types (`heading`, `paragraph`, `list`, `table`, `figure`, `code`, `callout`, `quote`, `divider`). Attributions are stored once at document level keyed by node `id` (not inline per block). Renderers walk the tree — `docx` writes paragraphs with style-mapped headings; `pptx` maps depth-1 sections to title slides, depth-2 sections to section dividers, leaves to content slides. Edit operations target a `node_id` and mutate the tree, persisting to `data/workspaces/<job_id>/document.json`.

**Tech Stack:** python-docx, python-pptx, Pillow (image embed), DeepSeek v4-flash via LiteLLM (block generation), DeepSeek v4-pro (edit reasoning, optional), existing SkillExecutor + handler.py dispatch, Prisma for source attribution lookup.

---

## File Structure

**Create:**
- `src/officeplane/content_agent/renderers/document.py` — new agnostic `Document`/`Section`/`Block` dataclasses + `parse_document()`
- `src/officeplane/content_agent/renderers/docx_render.py` — tree-walking docx renderer (replaces `docx_blocks.py`)
- `src/officeplane/content_agent/renderers/pptx_render.py` — tree-walking pptx renderer (replaces `pptx_blocks.py`)
- `src/officeplane/content_agent/document_ops.py` — `insert_node`, `replace_node`, `delete_node`, `find_node`, `walk_nodes`
- `src/officeplane/content_agent/skills/generate-docx/SKILL.md` + `handler.py` — replaces `generate-docx-blocks`
- `src/officeplane/content_agent/skills/generate-pptx/SKILL.md` + `handler.py` — replaces `generate-pptx-blocks`, accepts `slide_count`/`style`/`audience`/`tone`
- `src/officeplane/content_agent/skills/document-edit/SKILL.md` + `handler.py` — applies insert/replace/delete by `node_id`
- `tests/content_agent/test_document_tree.py` — parser + ops unit tests
- `tests/content_agent/test_renderers.py` — render-shape tests
- `tests/content_agent/test_e2e_bp.py` — end-to-end against staged BP doc

**Modify:**
- `src/officeplane/content_agent/skill_executor.py` — none expected; handler dispatch already works
- `data/test_bp.docx` — already staged

**Delete (post-migration only — Task 11):**
- `src/officeplane/content_agent/renderers/blocks.py`
- `src/officeplane/content_agent/renderers/docx_blocks.py`
- `src/officeplane/content_agent/renderers/pptx_blocks.py`
- `src/officeplane/content_agent/skills/generate-docx-blocks/`
- `src/officeplane/content_agent/skills/generate-pptx-blocks/`

---

### Task 1: Agnostic Document tree dataclasses

**Files:**
- Create: `src/officeplane/content_agent/renderers/document.py`
- Test: `tests/content_agent/test_document_tree.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_document_tree.py
from officeplane.content_agent.renderers.document import (
    Document, Section, Heading, Paragraph, List as ListBlock,
    Table, Figure, Code, Callout, Quote, Divider, Attribution,
    parse_document,
)


def test_parse_minimal_document():
    data = {
        "type": "document",
        "meta": {"title": "Hypertension Care"},
        "children": [
            {"type": "section", "level": 1, "heading": "Overview", "children": [
                {"type": "paragraph", "id": "p1", "text": "BP should be measured..."}
            ]}
        ],
        "attributions": [
            {"node_id": "p1", "document_id": "doc-1", "section_id": "sec-1"}
        ],
    }
    doc = parse_document(data)
    assert doc.meta.title == "Hypertension Care"
    assert len(doc.children) == 1
    section = doc.children[0]
    assert isinstance(section, Section)
    assert section.level == 1 and section.heading == "Overview"
    para = section.children[0]
    assert isinstance(para, Paragraph) and para.text.startswith("BP should")
    assert doc.attributions[0].node_id == "p1"


def test_recursive_sections_arbitrary_depth():
    data = {"type": "document", "children": [
        {"type": "section", "level": 1, "heading": "L1", "children": [
            {"type": "section", "level": 2, "heading": "L2", "children": [
                {"type": "section", "level": 3, "heading": "L3", "children": [
                    {"type": "paragraph", "text": "deep"}
                ]}
            ]}
        ]}
    ]}
    doc = parse_document(data)
    l3 = doc.children[0].children[0].children[0]
    assert isinstance(l3, Section) and l3.level == 3
    assert l3.children[0].text == "deep"


def test_all_block_types_round_trip():
    data = {"type": "document", "children": [
        {"type": "heading", "level": 2, "text": "H"},
        {"type": "paragraph", "text": "P"},
        {"type": "list", "ordered": True, "items": [{"type": "paragraph", "text": "i"}]},
        {"type": "table", "headers": ["c"], "rows": [["v"]]},
        {"type": "figure", "src": "img.png", "caption": "C"},
        {"type": "code", "lang": "py", "text": "print()"},
        {"type": "callout", "variant": "note", "text": "N"},
        {"type": "quote", "text": "Q"},
        {"type": "divider"},
    ]}
    doc = parse_document(data)
    types = [type(c).__name__ for c in doc.children]
    assert types == ["Heading", "Paragraph", "List", "Table", "Figure",
                     "Code", "Callout", "Quote", "Divider"]


def test_auto_assigns_node_ids():
    data = {"type": "document", "children": [
        {"type": "paragraph", "text": "no id"}
    ]}
    doc = parse_document(data)
    assert doc.children[0].id  # auto-assigned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/content_agent/test_document_tree.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'officeplane.content_agent.renderers.document'`

- [ ] **Step 3: Implement document tree**

Write `src/officeplane/content_agent/renderers/document.py` with:
- `DocumentMeta` (title, language, render_hints dict)
- `Attribution` (node_id, document_id, document_title, chapter_id, section_id, page_numbers)
- `Section` (id, level, heading, meta, children: list[Section|Block])
- Block dataclasses: `Heading(id, level, text)`, `Paragraph(id, text)`, `List(id, ordered, items)`, `Table(id, headers, rows)`, `Figure(id, src, caption, alt, prompt)`, `Code(id, lang, text)`, `Callout(id, variant, text)`, `Quote(id, text)`, `Divider(id)`
- `Document(meta, children, attributions)`
- `parse_document(data: dict) -> Document` — lenient parse, unknown types skipped, auto-assigns UUID4 short ids when missing

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/content_agent/test_document_tree.py -v`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/renderers/document.py tests/content_agent/test_document_tree.py
git commit -m "feat(content-agent): agnostic Document tree (CommonMark-aligned)"
```

---

### Task 2: Tree operations — find / insert / replace / delete

**Files:**
- Create: `src/officeplane/content_agent/document_ops.py`
- Test: `tests/content_agent/test_document_ops.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_document_ops.py
from officeplane.content_agent.renderers.document import (
    Document, Section, Paragraph, parse_document,
)
from officeplane.content_agent.document_ops import (
    find_node, insert_after, insert_before, insert_as_child,
    replace_node, delete_node, walk_nodes,
)


def _doc():
    return parse_document({"type": "document", "children": [
        {"type": "section", "id": "s1", "level": 1, "heading": "A", "children": [
            {"type": "paragraph", "id": "p1", "text": "one"},
            {"type": "paragraph", "id": "p2", "text": "two"},
        ]},
        {"type": "section", "id": "s2", "level": 1, "heading": "B", "children": []},
    ]})


def test_find_node_by_id():
    doc = _doc()
    node, parent = find_node(doc, "p2")
    assert isinstance(node, Paragraph) and node.text == "two"
    assert isinstance(parent, Section) and parent.id == "s1"


def test_insert_after_in_middle():
    doc = _doc()
    new = Paragraph(id="p1.5", text="between")
    insert_after(doc, anchor_id="p1", node=new)
    s1 = doc.children[0]
    assert [c.id for c in s1.children] == ["p1", "p1.5", "p2"]


def test_insert_before():
    doc = _doc()
    new = Paragraph(id="p0", text="zero")
    insert_before(doc, anchor_id="p1", node=new)
    s1 = doc.children[0]
    assert [c.id for c in s1.children] == ["p0", "p1", "p2"]


def test_insert_as_child_appends():
    doc = _doc()
    new = Paragraph(id="b1", text="B body")
    insert_as_child(doc, parent_id="s2", node=new)
    s2 = doc.children[1]
    assert [c.id for c in s2.children] == ["b1"]


def test_replace_node_in_place():
    doc = _doc()
    new = Paragraph(id="p1", text="REPLACED")
    replace_node(doc, target_id="p1", node=new)
    assert doc.children[0].children[0].text == "REPLACED"


def test_delete_node():
    doc = _doc()
    delete_node(doc, target_id="p1")
    assert [c.id for c in doc.children[0].children] == ["p2"]


def test_walk_yields_every_node_with_path():
    doc = _doc()
    paths = {node.id: path for node, path in walk_nodes(doc)}
    assert paths["p1"] == ["s1", "p1"]
    assert paths["s2"] == ["s2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/content_agent/test_document_ops.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ops module**

Write `src/officeplane/content_agent/document_ops.py`:
- `walk_nodes(doc) -> Iterator[tuple[Node, list[str]]]` — DFS, yields `(node, path_of_ids)`
- `find_node(doc, node_id) -> tuple[Node | None, Section | Document | None]` — returns (node, parent_container)
- `insert_after(doc, anchor_id, node)` / `insert_before(doc, anchor_id, node)` — sibling insert
- `insert_as_child(doc, parent_id, node, position: int | None = None)` — child append or insert at index
- `replace_node(doc, target_id, node)` — in-place swap, preserving siblings
- `delete_node(doc, target_id)` — remove from parent's children
- All ops raise `KeyError(node_id)` if not found

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/content_agent/test_document_ops.py -v`
Expected: PASS (7/7)

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/document_ops.py tests/content_agent/test_document_ops.py
git commit -m "feat(content-agent): document tree ops (find/insert/replace/delete/walk)"
```

---

### Task 3: DOCX tree renderer

**Files:**
- Create: `src/officeplane/content_agent/renderers/docx_render.py`
- Test: `tests/content_agent/test_docx_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_docx_render.py
import io
from docx import Document as DocxDocument
from officeplane.content_agent.renderers.document import parse_document
from officeplane.content_agent.renderers.docx_render import render_docx


def test_render_docx_writes_headings_and_paragraphs():
    doc = parse_document({"type": "document", "meta": {"title": "T"}, "children": [
        {"type": "section", "level": 1, "heading": "Intro", "children": [
            {"type": "paragraph", "text": "BP measurement matters."}
        ]},
        {"type": "section", "level": 1, "heading": "Method", "children": [
            {"type": "section", "level": 2, "heading": "Cuff", "children": [
                {"type": "paragraph", "text": "Use correct size."},
                {"type": "list", "ordered": True, "items": [
                    {"type": "paragraph", "text": "Small"},
                    {"type": "paragraph", "text": "Medium"},
                ]},
            ]}
        ]},
    ]})
    blob = render_docx(doc)
    assert isinstance(blob, bytes) and len(blob) > 1000
    out = DocxDocument(io.BytesIO(blob))
    texts = [p.text for p in out.paragraphs]
    assert "Intro" in texts
    assert "Cuff" in texts
    assert any("Small" in t for t in texts)


def test_render_docx_emits_table():
    doc = parse_document({"type": "document", "children": [
        {"type": "table",
         "headers": ["Systolic", "Diastolic"],
         "rows": [["120", "80"], ["140", "90"]]}
    ]})
    blob = render_docx(doc)
    out = DocxDocument(io.BytesIO(blob))
    assert len(out.tables) == 1
    assert out.tables[0].rows[0].cells[0].text == "Systolic"
    assert out.tables[0].rows[1].cells[1].text == "80"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/content_agent/test_docx_render.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement renderer**

Write `src/officeplane/content_agent/renderers/docx_render.py`:
- `render_docx(doc: Document) -> bytes` — uses `python-docx`
- Walk tree depth-first
- `Section` with `level` → call `docx.add_heading(text=heading, level=min(level, 9))`
- `Heading` block → `add_heading(text, level)`
- `Paragraph` → `add_paragraph(text)`
- `List` (ordered/unordered) → `add_paragraph(text, style="List Number"|"List Bullet")` per item
- `Table` → `add_table(rows=len(rows)+1, cols=len(headers))`, fill headers + cells
- `Figure` → if `src` is a base64 data URI or file path under `/data/`, embed via `add_picture`; caption as italic paragraph
- `Code` → `add_paragraph(text, style="No Spacing")` with monospace run
- `Callout` → bordered paragraph (simple: prefix with `[note]` style)
- `Quote` → `add_paragraph(text, style="Intense Quote")`
- `Divider` → page break
- Document title from `doc.meta.title` written as level-0 heading at start

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/content_agent/test_docx_render.py -v`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/renderers/docx_render.py tests/content_agent/test_docx_render.py
git commit -m "feat(content-agent): docx renderer walks Document tree"
```

---

### Task 4: PPTX tree renderer

**Files:**
- Create: `src/officeplane/content_agent/renderers/pptx_render.py`
- Test: `tests/content_agent/test_pptx_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_pptx_render.py
import io
from pptx import Presentation
from officeplane.content_agent.renderers.document import parse_document
from officeplane.content_agent.renderers.pptx_render import render_pptx


def test_render_pptx_one_slide_per_lowest_section():
    doc = parse_document({"type": "document", "meta": {"title": "BP Care"}, "children": [
        {"type": "section", "level": 1, "heading": "Why measure BP", "children": [
            {"type": "paragraph", "text": "Detect hypertension early."}
        ]},
        {"type": "section", "level": 1, "heading": "How to measure", "children": [
            {"type": "section", "level": 2, "heading": "Cuff selection", "children": [
                {"type": "paragraph", "text": "Pick correct size."}
            ]},
            {"type": "section", "level": 2, "heading": "Positioning", "children": [
                {"type": "paragraph", "text": "Arm at heart level."}
            ]},
        ]},
    ]})
    blob = render_pptx(doc)
    assert isinstance(blob, bytes) and len(blob) > 5000
    pres = Presentation(io.BytesIO(blob))
    # title slide + 3 content slides (Why measure BP, Cuff selection, Positioning)
    assert len(pres.slides) >= 4
    first_titles = [s.shapes.title.text for s in pres.slides if s.shapes.title]
    assert any("BP Care" in t for t in first_titles)
    assert any("Cuff selection" in t for t in first_titles)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/content_agent/test_pptx_render.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement renderer**

Write `src/officeplane/content_agent/renderers/pptx_render.py`:
- `render_pptx(doc: Document) -> bytes` — uses `python-pptx`
- Layout strategy:
  - Slide 0: title slide from `doc.meta.title`
  - For each leaf-bearing section (innermost section that contains block children, not just sub-sections): emit content slide with section `heading` as slide title, blocks as bullets/body text
  - For each non-leaf section at level 1 that contains sub-sections, emit a section-divider slide first
- Table block → render as native pptx table on its own slide
- Figure block with file path → `add_picture` on its own slide with caption
- List block → bullet content frame
- Code block → fixed-width text on its own slide
- Hard cap respect: if `doc.meta.render_hints["max_slides"]` set, truncate (warning printed)

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/content_agent/test_pptx_render.py -v`
Expected: PASS (1/1)

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/renderers/pptx_render.py tests/content_agent/test_pptx_render.py
git commit -m "feat(content-agent): pptx renderer walks Document tree, leaf-section-per-slide"
```

---

### Task 5: `generate-docx` skill (replaces `generate-docx-blocks`)

**Files:**
- Create: `src/officeplane/content_agent/skills/generate-docx/SKILL.md`
- Create: `src/officeplane/content_agent/skills/generate-docx/handler.py`
- Test: `tests/content_agent/test_skill_generate_docx.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_skill_generate_docx.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from officeplane.content_agent.skill_loader import load_skill
from officeplane.content_agent.skills.generate_docx.handler import handle


def test_handler_renders_real_docx(tmp_path, monkeypatch):
    fake_resp = MagicMock()
    fake_resp.content = (
        '{"type":"document","meta":{"title":"BP"},'
        '"children":[{"type":"section","level":1,"heading":"Intro",'
        '"children":[{"type":"paragraph","text":"text"}]}]}'
    )
    with patch("officeplane.content_agent.skills.generate_docx.handler._call_llm",
               return_value=fake_resp.content):
        with patch("officeplane.content_agent.skills.generate_docx.handler._load_sources",
                   return_value=[{"id": "x", "title": "Src", "text": "..."}]):
            result = handle(
                inputs={"source_document_ids": ["x"], "brief": "Make a doc"},
                workspace_dir=tmp_path,
            )
    assert result["file_path"].endswith(".docx")
    assert Path(result["file_path"]).exists()
    assert Path(result["file_path"]).stat().st_size > 1000
    assert result["title"] == "BP"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/content_agent/test_skill_generate_docx.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Create skill**

Create SKILL.md with the new schema in the prompt (no `modules/lessons` vocabulary). Schema in prompt:

```yaml
---
name: generate-docx
description: Generate a Word document from source documents using the agnostic Document tree
model: deepseek/deepseek-v4-flash
inputs:
  source_document_ids: list[str]    # required
  brief: str                        # required
  style: str                        # optional — e.g. "clinical", "casual", "technical"
  audience: str                     # optional
outputs:
  file_path: str
  title: str
  node_count: int
  model: str
---
```

Handler:
- Loads sources (text already extracted in ingestion) via Prisma
- Builds prompt asking DeepSeek for `Document` JSON tree (NEW schema with `type: document`, `children`, recursive `section`/`level`, leaf blocks)
- Parses via `parse_document`
- Calls `render_docx`
- Writes to `workspace_dir / "output.docx"`
- Returns `{file_path, title, node_count, model}`

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/content_agent/test_skill_generate_docx.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/skills/generate-docx/ tests/content_agent/test_skill_generate_docx.py
git commit -m "feat(skills): generate-docx skill emits agnostic Document tree"
```

---

### Task 6: `generate-pptx` skill — parameterised (slide_count / style / audience / tone)

**Files:**
- Create: `src/officeplane/content_agent/skills/generate-pptx/SKILL.md`
- Create: `src/officeplane/content_agent/skills/generate-pptx/handler.py`
- Test: `tests/content_agent/test_skill_generate_pptx.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_skill_generate_pptx.py
from pathlib import Path
from unittest.mock import patch
from officeplane.content_agent.skills.generate_pptx.handler import handle


def test_handler_respects_slide_count(tmp_path):
    json_tree = (
        '{"type":"document","meta":{"title":"BP",'
        '"render_hints":{"max_slides":8}},'
        '"children":[{"type":"section","level":1,"heading":"S","children":['
        + ",".join('{"type":"paragraph","text":"p"+str(i)+"\"}' for i in range(20))
        + "]}]}"
    )
    with patch("officeplane.content_agent.skills.generate_pptx.handler._call_llm",
               return_value=json_tree):
        with patch("officeplane.content_agent.skills.generate_pptx.handler._load_sources",
                   return_value=[{"id": "x", "title": "Src", "text": "..."}]):
            r = handle(
                inputs={
                    "source_document_ids": ["x"],
                    "brief": "Onboard nurses",
                    "slide_count": 8,
                    "style": "clinical",
                    "audience": "RNs",
                    "tone": "concise",
                },
                workspace_dir=tmp_path,
            )
    assert r["file_path"].endswith(".pptx")
    assert Path(r["file_path"]).exists()
    from pptx import Presentation
    pres = Presentation(r["file_path"])
    assert len(pres.slides) <= 8
    assert r["slide_count"] <= 8


def test_handler_threads_style_and_audience_into_prompt():
    captured = {}
    def fake_llm(prompt, **kw):
        captured["prompt"] = prompt
        return '{"type":"document","children":[]}'
    with patch("officeplane.content_agent.skills.generate_pptx.handler._call_llm",
               side_effect=fake_llm):
        with patch("officeplane.content_agent.skills.generate_pptx.handler._load_sources",
                   return_value=[]):
            handle(inputs={
                "source_document_ids": [],
                "brief": "Foo",
                "style": "clinical",
                "audience": "nurses",
                "tone": "warm",
                "slide_count": 12,
            }, workspace_dir=Path("/tmp"))
    p = captured["prompt"]
    assert "clinical" in p and "nurses" in p and "warm" in p and "12" in p
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/content_agent/test_skill_generate_pptx.py -v`
Expected: FAIL

- [ ] **Step 3: Create skill**

SKILL.md inputs:
```yaml
inputs:
  source_document_ids: list[str]
  brief: str
  slide_count: int = 10
  style: str = "professional"
  audience: str = "general"
  tone: str = "neutral"
outputs:
  file_path: str
  title: str
  slide_count: int
  model: str
```

Handler prompt threads `style`, `audience`, `tone`, `slide_count` into instructions. Sets `doc.meta.render_hints.max_slides = slide_count`. Returns actual rendered slide count.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/content_agent/test_skill_generate_pptx.py -v`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/skills/generate-pptx/ tests/content_agent/test_skill_generate_pptx.py
git commit -m "feat(skills): generate-pptx with slide_count/style/audience/tone params"
```

---

### Task 7: `document-edit` skill — insert / replace / delete at node_id

**Files:**
- Create: `src/officeplane/content_agent/skills/document-edit/SKILL.md`
- Create: `src/officeplane/content_agent/skills/document-edit/handler.py`
- Test: `tests/content_agent/test_skill_document_edit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_skill_document_edit.py
import json
from pathlib import Path
from officeplane.content_agent.skills.document_edit.handler import handle


def _seed_doc(workspace: Path):
    doc = {
        "type": "document", "meta": {"title": "T"},
        "children": [
            {"type": "section", "id": "s1", "level": 1, "heading": "A", "children": [
                {"type": "paragraph", "id": "p1", "text": "first"},
                {"type": "paragraph", "id": "p2", "text": "second"},
            ]}
        ],
        "attributions": [],
    }
    (workspace / "document.json").write_text(json.dumps(doc))


def test_insert_after(tmp_path):
    _seed_doc(tmp_path)
    r = handle(
        inputs={
            "operation": "insert_after",
            "anchor_id": "p1",
            "node": {"type": "paragraph", "id": "pNew", "text": "inserted"},
        },
        workspace_dir=tmp_path,
    )
    after = json.loads((tmp_path / "document.json").read_text())
    ids = [c["id"] for c in after["children"][0]["children"]]
    assert ids == ["p1", "pNew", "p2"]
    assert r["operation"] == "insert_after"


def test_replace(tmp_path):
    _seed_doc(tmp_path)
    handle(inputs={
        "operation": "replace",
        "target_id": "p1",
        "node": {"type": "paragraph", "id": "p1", "text": "CHANGED"},
    }, workspace_dir=tmp_path)
    after = json.loads((tmp_path / "document.json").read_text())
    assert after["children"][0]["children"][0]["text"] == "CHANGED"


def test_delete(tmp_path):
    _seed_doc(tmp_path)
    handle(inputs={"operation": "delete", "target_id": "p1"}, workspace_dir=tmp_path)
    after = json.loads((tmp_path / "document.json").read_text())
    assert [c["id"] for c in after["children"][0]["children"]] == ["p2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/content_agent/test_skill_document_edit.py -v`
Expected: FAIL

- [ ] **Step 3: Implement skill**

SKILL.md:
```yaml
inputs:
  operation: str    # "insert_after" | "insert_before" | "insert_as_child" | "replace" | "delete"
  anchor_id: str | None
  target_id: str | None
  parent_id: str | None
  node: dict | None
outputs:
  operation: str
  affected_node_id: str
  document_path: str
```

Handler:
- Loads `workspace_dir / "document.json"`
- Calls matching `document_ops` function
- Writes back
- Returns metadata

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/content_agent/test_skill_document_edit.py -v`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/skills/document-edit/ tests/content_agent/test_skill_document_edit.py
git commit -m "feat(skills): document-edit (insert/replace/delete by node_id)"
```

---

### Task 8: Image embedding pipeline — figure block + image-generation skill integration

**Files:**
- Modify: `src/officeplane/content_agent/skills/image-generation/handler.py` (or create if absent)
- Create: `src/officeplane/content_agent/image_embed.py` — helper that takes prompt, calls image-generation skill, returns local path
- Modify: `src/officeplane/content_agent/renderers/docx_render.py` and `pptx_render.py` — when Figure has `src` pointing to a local file under `/data/workspaces/`, embed it
- Test: `tests/content_agent/test_image_embed.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_image_embed.py
from unittest.mock import patch
from pathlib import Path
from officeplane.content_agent.image_embed import resolve_figure_image
from officeplane.content_agent.renderers.document import Figure


def test_resolve_figure_uses_existing_src(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 100)
    fig = Figure(id="f1", src=str(img), caption="Cap", alt="alt", prompt=None)
    path = resolve_figure_image(fig, workspace_dir=tmp_path)
    assert path == img


def test_resolve_figure_generates_from_prompt(tmp_path):
    fig = Figure(id="f1", src=None, caption=None, alt=None, prompt="diagram of cuff")
    fake_path = tmp_path / "generated.png"
    with patch("officeplane.content_agent.image_embed._invoke_image_generation",
               return_value=str(fake_path)) as m:
        fake_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 100)
        path = resolve_figure_image(fig, workspace_dir=tmp_path)
    m.assert_called_once()
    assert path == fake_path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/content_agent/test_image_embed.py -v`
Expected: FAIL

- [ ] **Step 3: Implement embedder**

Write `src/officeplane/content_agent/image_embed.py`:
- `resolve_figure_image(fig: Figure, workspace_dir: Path) -> Path | None`
  - If `fig.src` is set and file exists, return it
  - Else if `fig.prompt` set, dispatch `image-generation` skill via `SkillExecutor` or direct invoke, write result PNG to `workspace_dir / "images" / <fig.id>.png`, return that path
  - Else return `None`

Update `docx_render.py` and `pptx_render.py` to call this helper before embedding `Figure` blocks. Skip the figure if it returns `None`.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/content_agent/test_image_embed.py -v`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/content_agent/image_embed.py src/officeplane/content_agent/renderers/docx_render.py src/officeplane/content_agent/renderers/pptx_render.py tests/content_agent/test_image_embed.py
git commit -m "feat(content-agent): figure block resolves to src or image-generation prompt"
```

---

### Task 9: API endpoint smoke — wire new skills through `/api/jobs/invoke/`

**Files:**
- Verify (no changes expected): `src/officeplane/api/jobs.py` already dispatches any skill by name. No modification needed if Task 5/6/7 used handler.py pattern.

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_jobs_api.py
import os
import pytest
from fastapi.testclient import TestClient


@pytest.mark.skipif(not os.getenv("DEEPSEEK_API_KEY"), reason="needs DeepSeek")
def test_invoke_generate_docx(monkeypatch):
    from officeplane.api.main import app
    client = TestClient(app)
    # Use an ingested document id from the seeded DB
    r = client.post("/api/jobs/invoke/generate-docx", json={
        "inputs": {"source_document_ids": [], "brief": "Short summary about BP"}
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert "file_path" in j or "error" in j
```

- [ ] **Step 2: Run test**

Run: `docker compose exec -T api pytest tests/content_agent/test_jobs_api.py -v`
Expected: PASS (or skip if no key)

- [ ] **Step 3: Commit (test only)**

```bash
git add tests/content_agent/test_jobs_api.py
git commit -m "test(content-agent): smoke test new skills via /api/jobs/invoke/"
```

---

### Task 10: End-to-end live test with BP doc

**Files:**
- Create: `tests/content_agent/test_e2e_bp.py`

- [ ] **Step 1: Write the e2e test**

```python
# tests/content_agent/test_e2e_bp.py
import os
import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="requires DeepSeek + ingested BP doc",
)


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def _bp_id(client):
    r = client.get("/api/documents")
    for d in r.json():
        if "Measuring BP" in d.get("title", "") or "BP" in d.get("filename", ""):
            return d["id"]
    pytest.skip("BP doc not ingested yet")


def test_e2e_generate_docx_from_bp():
    c = _client()
    doc_id = _bp_id(c)
    r = c.post("/api/jobs/invoke/generate-docx", json={
        "inputs": {
            "source_document_ids": [doc_id],
            "brief": "Concise nurse-facing primer on home BP measurement",
            "audience": "RNs",
            "style": "clinical",
        }
    })
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["file_path"].endswith(".docx")
    assert out["node_count"] > 5


def test_e2e_generate_pptx_from_bp_with_slide_count():
    c = _client()
    doc_id = _bp_id(c)
    r = c.post("/api/jobs/invoke/generate-pptx", json={
        "inputs": {
            "source_document_ids": [doc_id],
            "brief": "Training deck for new clinic staff",
            "slide_count": 8,
            "style": "clinical",
            "audience": "MAs",
            "tone": "warm",
        }
    })
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["file_path"].endswith(".pptx")
    assert out["slide_count"] <= 8
```

- [ ] **Step 2: Ingest the BP doc**

Bash:
```bash
docker cp data/test_bp.docx officeplane-api:/tmp/test_bp.docx
docker exec officeplane-api python -m officeplane.cli.ingest /tmp/test_bp.docx
```
(or `curl -F file=@data/test_bp.docx http://localhost:8001/api/documents/upload`)

- [ ] **Step 3: Run the e2e test**

Run: `docker compose exec -T api pytest tests/content_agent/test_e2e_bp.py -v`
Expected: PASS (both produce real files)

- [ ] **Step 4: Manual smoke — open the output**

Bash:
```bash
ls -la data/workspaces/*/output.{docx,pptx}
```

- [ ] **Step 5: Commit**

```bash
git add tests/content_agent/test_e2e_bp.py
git commit -m "test(content-agent): e2e BP doc → docx + pptx with slide_count"
```

---

### Task 11: Delete legacy `*_blocks` modules

**Files:**
- Delete: `src/officeplane/content_agent/renderers/blocks.py`
- Delete: `src/officeplane/content_agent/renderers/docx_blocks.py`
- Delete: `src/officeplane/content_agent/renderers/pptx_blocks.py`
- Delete: `src/officeplane/content_agent/skills/generate-docx-blocks/`
- Delete: `src/officeplane/content_agent/skills/generate-pptx-blocks/`
- Delete: `tests/content_agent/test_generate_docx_blocks.py` (if present)
- Delete: `tests/content_agent/test_generate_pptx_blocks.py` (if present)

- [ ] **Step 1: Grep for residual imports**

```bash
grep -rn "BlocksDocument\|blocks_document\|generate-docx-blocks\|generate-pptx-blocks\|docx_blocks\|pptx_blocks" src/ tests/
```
Expected: only inside files being deleted.

- [ ] **Step 2: Delete legacy files**

```bash
git rm -r src/officeplane/content_agent/renderers/blocks.py \
          src/officeplane/content_agent/renderers/docx_blocks.py \
          src/officeplane/content_agent/renderers/pptx_blocks.py \
          src/officeplane/content_agent/skills/generate-docx-blocks \
          src/officeplane/content_agent/skills/generate-pptx-blocks
```

- [ ] **Step 3: Run full test suite**

Run: `docker compose exec -T api pytest tests/ -v`
Expected: same green count as before refactor (minus the deleted block-tests if any).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: drop legacy modules/lessons/blocks renderer + skills"
```

---

## Self-Review Checklist

- [ ] Vocabulary purge: no `modules`, `lessons`, `BlocksDocument` references left.
- [ ] Block taxonomy = CommonMark subset; documented in `document.py` module docstring.
- [ ] All edit ops are O(N) walk + mutate — acceptable for documents under ~10k nodes.
- [ ] `Figure.prompt` field added — required for image-generation integration.
- [ ] PPTX `slide_count` is a soft cap enforced in renderer (truncation), not just a prompt hint.
- [ ] E2E test against real BP doc covers both generation paths.
- [ ] DocSE Schema-version field on Document for future migration.
