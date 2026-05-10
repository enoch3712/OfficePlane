---
name: course-document
description: Block-based course content generation — schema v1.0 (modules → lessons → blocks). Use when writing course_content.json with text/title/table/image blocks grouped by lesson.
---

# Course Content Generation

Course content is a **lesson-based JSON structure** — NOT a prose document or markdown file.
Each module has `lessons[]`; each lesson has `blocks[]` that the Content Studio renders directly.

---

## Output Files

```
/workspace/course_content.json    ← primary output (schema v1.0: modules → lessons → blocks)
/workspace/images/                ← generated PNGs for image blocks
```

---

## Block Types

Four block types, in order of use within a module:

| Type | `content` field | When to use |
|------|-----------------|-------------|
| `title` | Plain string — the heading text | Section headings within a module |
| `text` | Plain string — paragraph prose | Explanations, concepts, summaries |
| `table` | JSON string — `{"headers":[…],"rows":[[…],…]}` | Definitions, comparisons, structured data |
| `image` | *(unused — use `alt` + `object_key`)* | Diagrams, illustrations per concept |

### ContentBlock schema

```json
{
  "id": "uuid-string",
  "type": "title" | "text" | "table" | "image",
  "content": "string or null",
  "order": 0,
  "url": null,
  "alt": "string or null",
  "object_key": "images/filename.png or null",
  "storage_bucket": null,
  "mime_type": "image/png or null",
  "source_references": [
    {
      "document_id": "<Document.id UUID>",
      "document_title": "<Document.title>",
      "chapter_id": "<Chapter.id UUID, optional>",
      "chapter_title": "<Chapter.title>",
      "section_id": "<Section.id UUID, optional>",
      "section_title": "<Section.title>",
      "page_numbers": [<int>, ...]
    }
  ]
}
```

`chapter_title` and `section_title` are required whenever a document structure is available.
They identify exactly which part of the source document this block is derived from.
The `document_id`, `chapter_id`, and `section_id` are UUIDs from OfficePlane's `documents`,
`chapters`, and `sections` tables respectively.

For `title` and `text` blocks: set `content`, leave `url`/`alt`/`object_key` null.
For `table` blocks: set `content` to a JSON string (see below), leave image fields null.
For `image` blocks: set `alt` and `object_key` (relative path in zip), leave `content`/`url` null.

---

## Output JSON Structure (schema v1.0)

```json
{
  "schema_version": "1.0",
  "modules": [
    {
      "id": "module-id-from-blueprint",
      "lessons": [
        {
          "id": "lesson-<uuid>",
          "title": "Welcome & Orientation",
          "order": 0,
          "blocks": [ ...blocks... ]
        }
      ]
    }
  ]
}
```

The module `id` must match the `id` from `course_blueprint.json`. Lesson IDs are yours
to invent but must be stable within a single run. Lessons are **your** responsibility —
the blueprint does not carry them; you split each module into 3–5 lessons.

---

## Block Sequence Per Lesson

For each lesson, generate blocks in this order:

```
1. title   → lesson topic heading (matches the lesson title)
2. text    → lesson hook (2–3 sentences introducing the learner's "why")
3. [for each concept/topic covered by this lesson:]
   title   → section name
   text    → instructional prose (minimum 120 words, grounded in source_text if available)
   table   → ONLY when the section compares/defines multiple items (definitions, comparisons)
4. image   → ≥1 Gemini illustration per lesson (see image-generation skill).
             Place it where it helps most — after the concept it illustrates, or near the top
             if it's a hero diagram for the whole lesson.
5. title   → "Lesson Summary"  (optional if the lesson is very short)
6. text    → 2–3 key takeaways as a short bulleted list
```

Floor: every lesson MUST have ≥1 `text` block AND ≥1 `image` block. Never produce a
lesson with no blocks or with only title blocks.

Adapt block count to lesson size — a short intro lesson might be 4 blocks, a deep-dive
lesson might be 10. Never inflate.

---

## Table Block Format

`content` must be a JSON **string** (stringified, not a nested object):

```python
import json

table_content = json.dumps({
    "headers": ["Term", "Definition"],
    "rows": [
        ["Deposit", "Money placed with a bank for safekeeping."],
        ["Interest Rate", "Percentage charged on borrowed funds annually."],
        ["Liquidity", "How quickly an asset can be converted to cash."]
    ]
})
# Store this string as the block's "content" field
```

---

## Generation Script

Write and run `/workspace/generate_content.py`:

```python
"""
Generate block-based course content from blueprint.
Run: python generate_content.py
Output: /workspace/course_content.json + /workspace/images/*.png
"""
import json, os, uuid
from pathlib import Path

BLUEPRINT_PATH      = "/workspace/references/course_blueprint.json"
LESSON_PLAN_PATH    = "/workspace/source/lesson_plan.json"
STRUCTURE_MAP_PATH  = "/workspace/source/lesson_structure_map.json"
OUTPUT_PATH         = "/workspace/course_content.json"
IMAGES_DIR          = "/workspace/images"

os.makedirs(IMAGES_DIR, exist_ok=True)

with open(BLUEPRINT_PATH) as f:
    blueprint = json.load(f)

# lesson_plan.json — your lesson split, produced in workflow step 2.
# Shape: { "<module_id>": [{"id": "...", "title": "...", "order": 0, "concept_ids": [...]}, ...] }
lesson_plan = {}
if Path(LESSON_PLAN_PATH).exists():
    with open(LESSON_PLAN_PATH) as f:
        lesson_plan = json.load(f)
    print(f"Loaded lesson plan: {sum(len(v) for v in lesson_plan.values())} lessons")
else:
    raise SystemExit(f"ERROR: {LESSON_PLAN_PATH} not found. Produce it in workflow step 2 before running this script.")

# Load the lesson-structure map produced by the document-search/document-extract step.
# Maps lesson ID → {document_id, document_title, chapter_id, chapter_title,
#                   section_id, section_title, page_numbers, selected_chapters}
# document_id, chapter_id, section_id are UUIDs from OfficePlane's documents/chapters/sections tables.
structure_map = {}
if Path(STRUCTURE_MAP_PATH).exists():
    with open(STRUCTURE_MAP_PATH) as f:
        structure_map = json.load(f)
    print(f"Loaded structure map: {len(structure_map)} lessons")

audience = blueprint.get("course_overview", {}).get("target_audience", "learners")


def load_lesson_source(module_order: int, lesson_order: int) -> str:
    """Load pre-fetched page content for a specific lesson, if available."""
    path = Path(f"/workspace/source/module_{module_order:02d}_lesson_{lesson_order:02d}_source.txt")
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text and not text.startswith("("):
            return text
    return ""


def build_refs(mapping: dict, topic: str = None) -> list:
    """Build source_references for a block, with chapter/section attribution.

    Args:
        mapping: Entry from structure_map for this module. Expected keys:
                 document_id (UUID), document_title, chapter_id (UUID, optional),
                 chapter_title, section_id (UUID, optional), section_title,
                 page_numbers ([int, ...]), selected_chapters ([{...}]).
        topic:   Optional keyword string (e.g. concept title) used to find the
                 most specific matching section. If None or no match, falls back
                 to the first selected chapter.

    Returns:
        List of source_reference dicts with document_id, document_title,
        chapter_id, chapter_title, section_id, section_title, and page_numbers —
        all filled to the most specific level available from OfficePlane's
        documents, chapters, and sections tables.
    """
    doc_id    = mapping.get("document_id")
    doc_title = mapping.get("document_title", "")
    chapters  = mapping.get("selected_chapters", [])

    if not doc_id or not chapters:
        return []

    best_chapter = chapters[0]
    best_section = None

    if topic:
        topic_lower = topic.lower()
        topic_words = set(w for w in topic_lower.split() if len(w) > 3)

        for ch in chapters:
            # Try to match a section first (most specific)
            for sec in ch.get("sections", []):
                sec_words = set(w for w in sec["section_title"].lower().split() if len(w) > 3)
                if sec_words & topic_words:
                    best_chapter = ch
                    best_section = sec
                    break
            if best_section:
                break

            # Fall back to chapter match
            ch_words = set(w for w in ch["chapter_title"].lower().split() if len(w) > 3)
            if ch_words & topic_words:
                best_chapter = ch

    # Determine the tightest page range available
    if best_section:
        pages        = best_section.get("page_numbers") or best_chapter.get("page_numbers")
        section_id   = best_section.get("section_id")
        section_title = best_section["section_title"]
    else:
        pages        = best_chapter.get("page_numbers")
        section_id   = best_chapter.get("sections", [{}])[0].get("section_id", "") if best_chapter.get("sections") else ""
        section_title = best_chapter.get("sections", [{}])[0].get("section_title", "") if best_chapter.get("sections") else ""

    return [{
        "document_id":    doc_id,
        "document_title": doc_title,
        "chapter_id":     best_chapter.get("chapter_id", ""),
        "chapter_title":  best_chapter.get("chapter_title", ""),
        "section_id":     section_id or "",
        "section_title":  section_title,
        "page_numbers":   pages,
    }]


def make_block(type_, *, content=None, alt=None, object_key=None,
               mime_type=None, order=0, source_refs=None):
    return {
        "id": str(uuid.uuid4()),
        "type": type_,
        "content": content,
        "order": order,
        "url": None,
        "alt": alt,
        "object_key": object_key,
        "storage_bucket": None,
        "mime_type": mime_type,
        "source_references": source_refs or [],
    }


def table_content(headers, rows):
    return json.dumps({"headers": headers, "rows": rows})


def generate_image_for_concept(concept_title, concept_description, audience, slug):
    """Generate concept illustration via Gemini. Returns object_key or None on failure."""
    out_path = f"{IMAGES_DIR}/{slug}.png"
    try:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "/workspace/generate_image.py",
             "--concept", concept_title,
             "--description", concept_description,
             "--audience", audience,
             "--out", out_path],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0 and Path(out_path).exists():
            print(f"  [image] generated: {out_path}")
            return f"images/{slug}.png"
        else:
            print(f"  [image] FAILED: {result.stderr[-300:]}")
            return None
    except Exception as exc:
        print(f"  [image] ERROR: {exc}")
        return None


def build_lesson_blocks(module, lesson, concepts_for_lesson, definitions_for_lesson):
    """Build blocks for a single lesson.

    Args:
        module: Module dict from blueprint (for module-level refs and audience).
        lesson: {"id", "title", "order", "concept_ids": [...]} from lesson_plan.
        concepts_for_lesson: Subset of blueprint concepts assigned to this lesson.
        definitions_for_lesson: Subset of blueprint definitions assigned to this lesson.

    Returns:
        List of block dicts for this lesson. MUST contain ≥1 text block AND ≥1 image block.
    """
    blocks = []
    order = 0

    mapping = structure_map.get(lesson["id"], {})
    lesson_ref = build_refs(mapping)

    source_text = load_lesson_source(module["order"], lesson["order"])
    has_source = bool(source_text)

    # 1. Lesson title
    blocks.append(make_block("title", content=lesson["title"],
                              order=order, source_refs=lesson_ref)); order += 1

    # 2. Hook — 2–3 sentence intro
    hook = (f"In this lesson you'll focus on {lesson['title']}. "
            "By the end, you'll be able to apply it in your own workflow.")
    blocks.append(make_block("text", content=hook.strip(),
                              order=order, source_refs=lesson_ref)); order += 1

    # 3. Concept sections — title + text per concept
    for concept in concepts_for_lesson:
        concept_ref = build_refs(mapping, topic=concept["title"])
        blocks.append(make_block("title", content=concept["title"],
                                  order=order, source_refs=concept_ref)); order += 1

        description = concept.get("description", "")
        bullets = concept.get("bullet_points", [])
        explanation = description
        if bullets:
            explanation += "\n\n" + "\n".join(f"- {b}" for b in bullets)
        blocks.append(make_block("text", content=explanation.strip(),
                                  order=order, source_refs=concept_ref)); order += 1

    # 4. Definitions table — if this lesson covers definition terms
    if definitions_for_lesson:
        def_ref = build_refs(mapping, topic=definitions_for_lesson[0]["term"])
        blocks.append(make_block("title", content="Key Definitions",
                                  order=order)); order += 1
        rows = [[d["term"], d["definition"]] for d in definitions_for_lesson]
        blocks.append(make_block("table",
                                  content=table_content(["Term", "Definition"], rows),
                                  order=order, source_refs=def_ref)); order += 1

    # 5. Lesson image — REQUIRED: every lesson has ≥1 Gemini illustration.
    image_concept = concepts_for_lesson[0] if concepts_for_lesson else {"title": lesson["title"], "description": lesson["title"]}
    slug = lesson["id"].lower().replace("-", "_")[:48]
    img_desc = image_concept.get("description", image_concept["title"])
    obj_key = generate_image_for_concept(image_concept["title"], img_desc, audience, slug)
    if obj_key:
        concept_ref = build_refs(mapping, topic=image_concept["title"])
        blocks.append(make_block("image",
                                  alt=f"{image_concept['title']} illustration",
                                  object_key=obj_key,
                                  mime_type="image/png",
                                  order=order, source_refs=concept_ref)); order += 1
    else:
        # Image generation failed — retry once with a broader concept description
        print(f"  [image] retry for lesson {lesson['id']}")
        obj_key = generate_image_for_concept(lesson["title"],
                                              f"{lesson['title']} for {audience}",
                                              audience, f"{slug}_retry")
        if obj_key:
            blocks.append(make_block("image",
                                      alt=f"{lesson['title']} illustration",
                                      object_key=obj_key,
                                      mime_type="image/png",
                                      order=order, source_refs=lesson_ref)); order += 1

    # Enforce the ≥1 image floor — fail loudly if we still have none.
    has_image = any(b["type"] == "image" for b in blocks)
    if not has_image:
        raise RuntimeError(
            f"Lesson {lesson['id']} (module {module['id']}) has no image block. "
            "Image generation failed twice — check GOOGLE_API_KEY and generate_image.py."
        )

    return blocks


# ── Build output ──────────────────────────────────────────────────────────────

output = {"schema_version": "1.0", "modules": []}

for module in blueprint.get("modules", []):
    lessons = lesson_plan.get(module["id"], [])
    if not lessons:
        raise SystemExit(f"ERROR: module {module['id']} has no lessons in lesson_plan.json")
    print(f"Processing module: {module['title']} ({len(lessons)} lessons)")

    module_concepts = module.get("concepts", [])
    module_definitions = module.get("definitions", [])

    out_lessons = []
    for lesson in lessons:
        concept_ids = set(lesson.get("concept_ids") or [])
        concepts_for_lesson = [c for c in module_concepts if c.get("id") in concept_ids] \
            if concept_ids else module_concepts[: max(1, len(module_concepts) // max(1, len(lessons)))]
        definitions_for_lesson = [d for d in module_definitions if d.get("lesson_id") == lesson["id"]] \
            if any(d.get("lesson_id") for d in module_definitions) else module_definitions if lesson["order"] == 0 else []

        print(f"  Lesson: {lesson['title']} ({len(concepts_for_lesson)} concepts)")
        blocks = build_lesson_blocks(module, lesson, concepts_for_lesson, definitions_for_lesson)
        out_lessons.append({
            "id": lesson["id"],
            "title": lesson["title"],
            "order": lesson["order"],
            "blocks": blocks,
        })
        print(f"    → {len(blocks)} blocks generated")

    output["modules"].append({
        "id": module["id"],
        "lessons": out_lessons,
    })

with open(OUTPUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print(f"\nDone. Output: {OUTPUT_PATH}")
print(f"Schema:  {output['schema_version']}")
print(f"Modules: {len(output['modules'])}")
print(f"Lessons: {sum(len(m['lessons']) for m in output['modules'])}")
print(f"Images:  {len(list(Path(IMAGES_DIR).glob('*.png')))}")
```

---

## Image Generation Script

Save as `/workspace/generate_image.py` — called by `generate_content.py` above.

```python
"""Generate one educational illustration via Gemini with quality review loop.

Usage:
  python generate_image.py \
    --concept "Supply Chain Risk" \
    --description "A flowchart showing supplier → manufacturer → distributor → retailer,
                   with red warning icons at each risk checkpoint." \
    --audience "procurement managers" \
    --out /workspace/images/supply_chain_risk.png
"""
import argparse, base64, json, os, sys, time
from io import BytesIO

_GEN_MODEL     = "gemini-3.1-flash-image-preview"
_REVIEW_MODEL  = "gemini-3-flash-preview"
_QUALITY_LOOPS = 3
_MIN_SCORE     = 0.8


def _client():
    from google import genai
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        sys.exit("ERROR: GOOGLE_API_KEY is required.")
    return genai.Client(api_key=key)


def _gen_prompt(concept, description, audience, feedback=None):
    parts = [
        f"Create a professional educational illustration for: '{concept}'.\n"
        f"AUDIENCE: {audience}\n\n"
        f"VISUAL DESCRIPTION:\n{description}\n\n"
        "REQUIREMENTS:\n"
        "- Clean, professional style for a corporate training document\n"
        "- Clear labels and annotations\n"
        "- High contrast, readable text\n"
        "- No photorealistic people — use icons, shapes, diagrams\n"
        "- White or very light background\n"
        "- 16:9 aspect ratio"
    ]
    if feedback:
        parts.append(f"\nFIX THESE ISSUES FROM PREVIOUS ATTEMPT:\n{feedback}")
    return "\n".join(parts)


def _review_prompt(concept, description):
    return (
        f"Review this educational illustration for: '{concept}'.\n"
        f"It was supposed to show: {description}\n\n"
        "Score 0.0–1.0 each:\n"
        "1. ACCURACY: Does it correctly illustrate the concept?\n"
        "2. CLARITY: Clear and easy to understand at a glance?\n"
        "3. PROFESSIONAL: Polished, suitable for corporate training?\n"
        "4. TEXT_QUALITY: Text readable and correct? (1.0 if no text)\n\n"
        "Respond ONLY with valid JSON:\n"
        '{"accuracy":0.0,"clarity":0.0,"professional":0.0,"text_quality":1.0,'
        '"composite":0.0,"needs_repeat":false,"critique":"","action_items":[]}'
    )


def generate(concept, description, audience, out_path):
    from google import genai
    from google.genai import types
    client = _client()
    best_data, best_score, feedback = None, -1.0, None

    for iteration in range(1, _QUALITY_LOOPS + 1):
        print(f"[image] iter {iteration}/{_QUALITY_LOOPS}", flush=True)
        image_data = None

        for attempt in range(3):
            try:
                for chunk in client.models.generate_content_stream(
                    model=_GEN_MODEL,
                    contents=[types.Content(role="user",
                        parts=[types.Part.from_text(text=_gen_prompt(concept, description, audience, feedback))])],
                    config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
                ):
                    if not (chunk.candidates and chunk.candidates[0].content
                            and chunk.candidates[0].content.parts):
                        continue
                    for part in chunk.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data and image_data is None:
                            raw = part.inline_data.data
                            image_data = base64.b64decode(raw) if isinstance(raw, str) else raw
                if image_data:
                    break
            except Exception as exc:
                wait = 2 ** attempt
                print(f"[image] attempt {attempt+1} failed: {exc}, retry in {wait}s")
                time.sleep(wait)

        if not image_data:
            if best_data:
                print("[image] failed, using best so far"); break
            sys.exit("[image] ERROR: generation failed after 3 attempts")

        if best_data is None:
            best_data = image_data

        if iteration == _QUALITY_LOOPS:
            best_data = image_data; break

        try:
            g64 = base64.b64encode(image_data).decode("ascii")
            resp = client.models.generate_content(
                model=_REVIEW_MODEL,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_text(text=_review_prompt(concept, description)),
                    types.Part.from_bytes(data=base64.b64decode(g64), mime_type="image/png"),
                ])],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.0),
            )
            text = (resp.text or "").strip().strip("```json").strip("```").strip()
            review = json.loads(text)
            composite = float(review.get("composite", 0.0))
            print(f"[image] review composite={composite:.2f} needs_repeat={review.get('needs_repeat')}")
            if composite > best_score:
                best_score, best_data = composite, image_data
            if not review.get("needs_repeat") or composite >= _MIN_SCORE:
                break
            fb = []
            if review.get("critique"): fb.append(review["critique"])
            if review.get("action_items"): fb.append(str(review["action_items"]))
            feedback = "\n".join(fb) or None
        except Exception as exc:
            print(f"[image] review failed: {exc}"); best_data = image_data; break

    try:
        from PIL import Image
        img = Image.open(BytesIO(best_data))
        if img.width < 1920:
            img = img.resize((1920, int(img.height * 1920 / img.width)), Image.LANCZOS)
        img.save(out_path, format="PNG")
    except Exception:
        with open(out_path, "wb") as fh:
            fh.write(best_data)
    print(f"[image] saved → {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--concept", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--audience", default="learners")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    generate(args.concept, args.description, args.audience, args.out)
```

---

## Writing Good Image Descriptions

The `--description` (and `concept.description` in the blueprint) drives image quality. Be specific:

| Good | Bad |
|------|-----|
| "A 3×3 grid showing Likelihood (x-axis) vs Impact (y-axis), cells color-coded green/yellow/red" | "A risk matrix" |
| "A circular PDCA flow: Plan→Do→Check→Act with arrows and a small icon per stage" | "PDCA diagram" |
| "A hierarchy tree: Company at top → 3 Departments → Teams, each as a rounded box" | "Org chart" |

---

## Generation Workflow

```
1. Install deps and copy scripts
   uv pip install google-genai Pillow 2>/dev/null || true
   # Write generate_image.py to /workspace/generate_image.py
   # Write generate_content.py to /workspace/generate_content.py

2. Run
   python /workspace/generate_content.py

3. Verify
   python -c "
   import json
   with open('/workspace/course_content.json') as f: d = json.load(f)
   assert d.get('schema_version') == '1.0'
   for m in d['modules']:
       for l in m.get('lessons', []):
           types = [b['type'] for b in l.get('blocks', [])]
           assert 'image' in types, f'lesson {l[\"id\"]} has no image'
           assert 'text'  in types, f'lesson {l[\"id\"]} has no text'
           print(m['id'][:8], '/', l['id'][:12], '->', types)
   "

4. Check images
   ls -lh /workspace/images/*.png

5. Package
   cd /workspace && zip -r results.zip course_content.json images/ \
     -x '*.pyc' -x '__pycache__/*' -x 'results.zip'
```

---

## Quality Checklist

- [ ] `course_content.json` exists and is valid JSON
- [ ] Top-level `schema_version: "1.0"` is present
- [ ] Every module from the blueprint has an entry in `modules[]`
- [ ] Module `id` values match blueprint exactly
- [ ] Every module has a non-empty `lessons[]` array (3–5 lessons typical)
- [ ] Every lesson has a unique `id`, a `title`, a numeric `order`, and a `blocks[]` array
- [ ] Every lesson has ≥1 `text` block AND ≥1 `image` block (hard floor)
- [ ] Every `image` block has a matching `.png` in `/workspace/images/` ≥200KB
- [ ] Every `table` block has valid JSON in `content` (`{"headers":[],"rows":[[]]}`)
- [ ] No block has empty `content` (use `null` for image blocks, never `""`)
- [ ] `order` is sequential starting from 0 within each lesson
- [ ] `lesson.order` is sequential starting from 0 within each module
- [ ] Every `source_references` entry uses `document_id`/`chapter_id`/`section_id` UUIDs from OfficePlane's tables (not legacy `document_structure_id`)

---

## NEVER

- NEVER output a prose markdown document — output is always `course_content.json`
- NEVER use the legacy flat `generated_content[]` per module — every module MUST carry `lessons[]`
- NEVER mix module IDs — use the exact `id` from `course_blueprint.json`
- NEVER put raw HTML or markdown inside `content` strings — plain text only
- NEVER skip the image block for a lesson — ≥1 image per lesson is a hard floor
- NEVER parse PDF/DOCX/PPTX directly — fetch content via OfficePlane's document-search and document-extract ECM tools
- NEVER leave `content` as an empty string `""` — use `null` for non-text blocks
- NEVER use `document_structure_id` in source_references — use `document_id`, `chapter_id`, `section_id` with OfficePlane UUIDs
