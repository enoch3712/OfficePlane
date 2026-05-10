---
name: image-generation
description: Generate educational illustrations via Google Gemini. Use the pre-installed /app/scripts/generate_image.py — never draw with matplotlib or PIL.ImageDraw for illustrations.
---

# Image Generation Skill (Gemini)

Generate professional educational illustrations using Google Gemini's image generation API.
The script is **pre-installed** at `/app/scripts/generate_image.py` — do NOT write your own.

---

## Image Planning Rules

Images are expensive and should be used strategically. **Plan before generating.**

### Density Rule

**Maximum 1 image per 3 pages of content.** Count the total content blocks for a module,
estimate pages (roughly 3–4 text blocks per page), and calculate the image budget.

```
image_budget = max(1, total_estimated_pages // 3)
```

Examples:
- 4-page module → 1 image
- 6-page module → 2 images
- 10-page module → 3 images
- 1-page module → 1 image (minimum 1 if concepts exist)

### Which Concepts Get Images

Not every concept needs an image. Pick the ones where a visual adds the most value:

1. **Processes or workflows** — flowcharts, step-by-step sequences
2. **Classifications or categories** — color-coded charts, comparison grids
3. **Spatial or structural concepts** — anatomy, equipment diagrams, layouts
4. **Data comparisons** — bar charts, before/after, side-by-side

Skip images for concepts that are purely definitional or abstract (e.g., "What is tax evasion?").

### Planning Step

Before generating any images, write an image plan:

```python
# In generate_content.py, before building blocks:
concepts_with_images = []
for concept in concepts:
    # Score: does this concept benefit from a visual?
    desc = concept.get("description", "").lower()
    visual_keywords = ["diagram", "chart", "flow", "compare", "classify", "step", "process", "anatomy", "structure", "table"]
    if any(kw in desc for kw in visual_keywords) or any(kw in concept["title"].lower() for kw in visual_keywords):
        concepts_with_images.append(concept)

# Respect budget
concepts_with_images = concepts_with_images[:image_budget]
```

---

## Default Visual Style

Until brand-specific style guides are configured, **all images use this default style:**

```
STYLE GUIDE — Default (Colibri Education)
──────────────────────────────────────────
Layout:       Clean, flat design. White or very light (#F8F9FA) background.
Colors:       Primary #2563EB (blue), Accent #10B981 (green), Warning #F59E0B (amber),
              Danger #EF4444 (red), Neutral #6B7280 (gray). Use sparingly — max 4 colors per image.
Typography:   Sans-serif labels only. Bold for headings, regular for annotations.
              Minimum font size that is readable at 50% zoom.
Icons:        Simple geometric shapes and line icons. No photorealistic imagery.
              No people — use abstract figures, silhouettes, or role labels instead.
People:       NEVER show photorealistic people. Use labeled boxes, stick figures, or role icons.
Aspect ratio: 16:9 (1920×1080 target)
Borders:      Subtle rounded corners (8px). Light gray (#E5E7EB) borders where needed.
Whitespace:   Generous padding. Never crowd elements. 10% margin on all sides minimum.
Annotations:  Clear callout labels with leader lines. No decorative elements.
```

Append this style block to every `--description` passed to `generate_image.py`:

```python
DEFAULT_STYLE = (
    "\n\nSTYLE: Clean flat design on white background. "
    "Colors: blue (#2563EB) primary, green (#10B981) accent, amber (#F59E0B) warning, "
    "red (#EF4444) danger. Sans-serif labels. No photorealistic people — use icons and shapes. "
    "16:9 aspect ratio. Generous whitespace. Rounded corners. Professional and minimal."
)

# When calling generate_image.py:
full_description = concept_description + DEFAULT_STYLE
```

---

## Setup

```bash
# Copy the pre-installed script to workspace (once at start)
cp /app/scripts/generate_image.py /workspace/generate_image.py
```

## Usage

```bash
python /workspace/generate_image.py \
  --concept "Blood Pressure Classification" \
  --description "A color-coded chart showing Normal, Elevated, Stage 1, Stage 2, Crisis categories with BP ranges. STYLE: Clean flat design on white background. Colors: blue primary, green accent, amber warning, red danger. Sans-serif labels. No people. 16:9. Generous whitespace." \
  --audience "healthcare professionals" \
  --out /workspace/images/bp_classification.png
```

## Environment Variables

```bash
echo $GOOGLE_API_KEY   # Required — Gemini API key
```

## Using from generate_content.py

```python
DEFAULT_STYLE = (
    "\n\nSTYLE: Clean flat design on white background. "
    "Colors: blue (#2563EB) primary, green (#10B981) accent, amber (#F59E0B) warning, "
    "red (#EF4444) danger. Sans-serif labels. No photorealistic people — use icons and shapes. "
    "16:9 aspect ratio. Generous whitespace. Rounded corners. Professional and minimal."
)

def generate_image_for_concept(concept_title, concept_description, audience, slug):
    """Generate concept illustration via Gemini. Returns object_key or None."""
    out_path = f"{IMAGES_DIR}/{slug}.png"
    full_description = concept_description + DEFAULT_STYLE
    try:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "/workspace/generate_image.py",
             "--concept", concept_title,
             "--description", full_description,
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
```

## Writing Good Descriptions

The `--description` drives image quality. Be specific about what to show:

| Good | Bad |
|------|-----|
| "A color-coded BP classification chart: green Normal (<120/80), yellow Elevated, orange Stage 1, red Stage 2, dark red Crisis" | "A blood pressure chart" |
| "A diagram of an arm with a BP cuff at heart level, arrows showing bladder covers 80% of arm circumference" | "A cuff diagram" |
| "A flowchart: Patient arrives → Rest 5 min → Select cuff → Position arm → Take 2 readings → Average" | "BP measurement steps" |

---

## NEVER

- NEVER write your own image generation script — use `/app/scripts/generate_image.py`
- NEVER generate placeholder images with matplotlib — always use Gemini
- NEVER exceed the image budget (1 per 3 pages)
- NEVER generate images for purely definitional concepts — only for visual ones
- NEVER use generic descriptions — be specific about layout, colors, labels, and style
- NEVER omit the default style suffix from descriptions

---

## OfficePlane integration

When this skill runs inside OfficePlane:
- The agent has access to ECM tools through the SkillExecutor (Phase 7+ tool layer).
- Generated artifacts should be written under the workspace passed by the runner.
- Source content should cite the originating Document/Chapter/Section IDs in any output JSON.
