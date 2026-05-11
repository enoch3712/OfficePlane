---
sidebar_position: 7
title: "Skills: SKILL.md Filesystem Catalog"
---

# Skills: SKILL.md Filesystem Catalog

Skills are the unit of capability in OfficePlane. Each skill is a directory on the filesystem containing a `SKILL.md` manifest and optionally a `handler.py` for custom execution logic. The agent runtime discovers skills at startup by scanning the skills directory.

## SKILL.md Format

Every skill directory must contain a `SKILL.md` with YAML frontmatter:

```markdown
---
name: generate-docx
description: Generate a Word document from a structured prompt
model: flash
tier: flash
inputs:
  - name: topic
    type: string
    required: true
    description: Subject matter of the document
  - name: page_count
    type: integer
    required: false
    default: 5
    description: Target page count
outputs:
  - name: document_id
    type: string
    description: ID of the generated document
  - name: download_url
    type: string
    description: Presigned URL for the DOCX file
tools:
  - bash
  - write_file
---

Generate a well-structured Word document on the given topic.
Use headings, paragraphs, and tables as appropriate.
Emit a JSON document tree conforming to schema_version 1.0.
```

### Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Kebab-case identifier, used in API paths |
| `description` | string | yes | One-line summary shown in the skills catalog endpoint |
| `model` | `flash` \| `pro` | yes | Which model tier to use (see [Models](/architecture/models-and-tiers)) |
| `tier` | `flash` \| `pro` | yes | Alias for `model`; both fields must match |
| `inputs` | list of dicts | yes | Input parameter schema |
| `outputs` | list of dicts | yes | Output parameter schema |
| `tools` | list of strings | no | Explicit tool allowlist; omit to allow all tools |

`inputs` and `outputs` entries each take: `name`, `type`, `required`, `default` (optional), `description`.

## handler.py Dispatch

When a skill directory contains a `handler.py` with an `async def execute` function, the runtime calls it directly instead of falling back to the LLM prompt path:

```python
# skills/generate-docx/handler.py

async def execute(*, inputs: dict, **_) -> dict:
    topic = inputs["topic"]
    page_count = inputs.get("page_count", 5)

    # Build the document tree, persist to DB, return IDs
    doc = await build_document(topic, page_count)
    url = await render_docx(doc.id)

    return {
        "document_id": doc.id,
        "download_url": url,
    }
```

If `handler.py` is absent, the runtime sends the `SKILL.md` body as a system prompt to the configured model and parses the structured response against the `outputs` schema.

The `**_` catch-all in the signature is intentional — the runtime may pass additional keyword arguments (context, run ID, etc.) in future versions.

## Shipped Skills

### ECM Operations

| Skill | Description |
|-------|-------------|
| `ingest-document` | Upload a file and run the full vision ingestion pipeline |
| `search-documents` | Semantic search across all ingested documents using pgvector |
| `export-document` | Export a document to DOCX, PPTX, PDF, or Markdown |
| `delete-document` | Soft-delete a document and its associated revisions |
| `list-documents` | Paginated listing with metadata filters |

### Content Generation

| Skill | Description |
|-------|-------------|
| `generate-docx` | Generate a Word document from a topic + page count |
| `generate-pptx` | Generate a PowerPoint presentation with slide count, style, audience, and tone |
| `generate-report` | Generate a structured report with executive summary, findings, and appendices |
| `summarize-document` | Produce a multi-level summary (one-paragraph, one-page, executive) |
| `translate-document` | Translate a document's text blocks into a target language |
| `expand-section` | Expand a short section into a full draft |

### Document Editing

| Skill | Description |
|-------|-------------|
| `document-edit` | Apply a single structural edit operation to a document node |
| `document-edit-batch` | Apply a list of operations atomically |
| `rewrite-block` | Rewrite a single block with a style or tone directive |
| `insert-table` | Insert a formatted table at a target node anchor |
| `insert-figure` | Insert an image block with caption |
| `restructure-sections` | Reorder or merge sections by ID list |

### Image Generation

| Skill | Description |
|-------|-------------|
| `generate-image` | Generate an image from a text prompt and store it as a figure block |
| `generate-diagram` | Generate a Mermaid or PlantUML diagram and embed it |

### Compliance and Review

| Skill | Description |
|-------|-------------|
| `compliance-check` | Run a document through a configurable compliance ruleset |
| `style-review` | Check writing style against a house style guide |
| `fact-check-section` | Cross-reference claims in a section against source documents |
| `similarity-check` | Detect near-duplicate content across the document corpus |

### Utilities

| Skill | Description |
|-------|-------------|
| `extract-tables` | Extract all tables from a document as JSON arrays |
| `merge-documents` | Merge two or more documents into one, preserving lineage |
| `split-document` | Split a document at a section boundary into two new documents |

## Authoring a New Skill

1. **Create the directory:**
   ```bash
   mkdir -p skills/my-skill
   ```

2. **Write the manifest:**
   ```markdown
   # skills/my-skill/SKILL.md
   ---
   name: my-skill
   description: One-line description
   model: flash
   tier: flash
   inputs:
     - name: input_text
       type: string
       required: true
       description: The input to process
   outputs:
     - name: result
       type: string
       description: Processed output
   ---

   Process the input_text and return a cleaned result.
   Apply the following rules: ...
   ```

3. **Optionally add a handler:**

   If the skill needs to call internal APIs, read from the database, or perform multi-step logic that is impractical to express in a prompt, add `handler.py`:

   ```python
   # skills/my-skill/handler.py

   async def execute(*, inputs: dict, **_) -> dict:
       result = process(inputs["input_text"])
       return {"result": result}
   ```

4. **Register via the API** (skills are auto-discovered on startup, but you can force a reload):
   ```bash
   curl -X POST http://localhost:8001/api/skills/reload
   ```

5. **Invoke the skill:**
   ```bash
   curl -X POST http://localhost:8001/api/jobs/invoke/my-skill \
     -H "Content-Type: application/json" \
     -d '{"input_text": "hello world"}'
   ```

The runtime validates inputs against the `SKILL.md` schema before dispatch, so handler errors are never caused by missing required fields.
