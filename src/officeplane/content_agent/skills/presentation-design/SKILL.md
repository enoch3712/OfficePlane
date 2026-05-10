---
name: presentation-design
description: Create polished PPTX presentations with pptxgenjs. Includes color palettes, typography rules, layout patterns, QA workflow, and rendering commands.
---

# PPTX Skill

## Quick Reference

| Task | Guide |
|------|-------|
| Read/analyze content | `python -m markitdown presentation.pptx` |
| Create from scratch | Use pptxgenjs (Node.js) for best results |
| Convert to images | `soffice --headless --convert-to pdf` then `pdftoppm` |

---

## Creating from Scratch (pptxgenjs)

Use Node.js `pptxgenjs` for creating presentations — it produces better layouts than python-pptx.

```bash
npm install pptxgenjs
```

Write a Node.js script that creates the deck, then run it:
```bash
node create_deck.js
```

### pptxgenjs Quick API

```javascript
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();

// Set 16:9
pres.defineLayout({ name: "WIDE", width: 13.33, height: 7.5 });
pres.layout = "WIDE";

// Add slide
const slide = pres.addSlide();

// Background
slide.background = { color: "1E2761" };

// Text
slide.addText("Title Here", {
  x: 0.8, y: 0.5, w: 11.7, h: 1.2,
  fontSize: 44, fontFace: "Georgia", color: "FFFFFF", bold: true
});

// Shapes
slide.addShape(pres.ShapeType.rect, {
  x: 0.8, y: 2.0, w: 5.5, h: 3.5,
  fill: { color: "CADCFC" }, rectRadius: 0.15
});

// Images (embed from file)
slide.addImage({ path: "/workspace/references/logo.png", x: 1, y: 1, w: 2, h: 2 });

// Save
pres.writeFile({ fileName: "/workspace/output.pptx" });
```

---

## Design Ideas

**Don't create boring slides.** Plain bullets on a white background won't impress anyone.

### Before Starting

- **Pick a bold, content-informed color palette**: The palette should feel designed for THIS topic. If swapping your colors into a completely different presentation would still "work," you haven't made specific enough choices.
- **Dominance over equality**: One color should dominate (60-70% visual weight), with 1-2 supporting tones and one sharp accent. Never give all colors equal weight.
- **Dark/light contrast**: Dark backgrounds for title + conclusion slides, light for content ("sandwich" structure). Or commit to dark throughout for a premium feel.
- **Commit to a visual motif**: Pick ONE distinctive element and repeat it — rounded image frames, icons in colored circles, thick single-side borders. Carry it across every slide.

### Color Palettes

| Theme | Primary | Secondary | Accent |
|-------|---------|-----------|--------|
| Midnight Executive | `1E2761` (navy) | `CADCFC` (ice blue) | `FFFFFF` (white) |
| Forest & Moss | `2C5F2D` (forest) | `97BC62` (moss) | `F5F5F5` (cream) |
| Coral Energy | `F96167` (coral) | `F9E795` (gold) | `2F3C7E` (navy) |
| Warm Terracotta | `B85042` (terracotta) | `E7E8D1` (sand) | `A7BEAE` (sage) |
| Ocean Gradient | `065A82` (deep blue) | `1C7293` (teal) | `21295C` (midnight) |
| Charcoal Minimal | `36454F` (charcoal) | `F2F2F2` (off-white) | `212121` (black) |
| Teal Trust | `028090` (teal) | `00A896` (seafoam) | `02C39A` (mint) |
| Berry & Cream | `6D2E46` (berry) | `A26769` (dusty rose) | `ECE2D0` (cream) |
| Sage Calm | `84B59F` (sage) | `69A297` (eucalyptus) | `50808E` (slate) |
| Cherry Bold | `990011` (cherry) | `FCF6F5` (off-white) | `2F3C7E` (navy) |

### For Each Slide

**Every slide needs a visual element** — image, chart, icon, or shape. Text-only slides are forgettable.

**Layout options:**
- Two-column (text left, illustration on right)
- Icon + text rows (icon in colored circle, bold header, description below)
- 2x2 or 2x3 grid (image on one side, grid of content blocks on other)
- Half-bleed image (full left or right side) with content overlay

**Data display:**
- Large stat callouts (big numbers 60-72pt with small labels below)
- Comparison columns (before/after, pros/cons, side-by-side options)
- Timeline or process flow (numbered steps, arrows)

**Visual polish:**
- Icons in small colored circles next to section headers
- Italic accent text for key stats or taglines

### Typography

| Header Font | Body Font |
|-------------|-----------|
| Georgia | Calibri |
| Arial Black | Arial |
| Calibri | Calibri Light |
| Cambria | Calibri |
| Trebuchet MS | Calibri |
| Impact | Arial |
| Palatino | Garamond |
| Consolas | Calibri |

| Element | Size |
|---------|------|
| Slide title | 36-44pt bold |
| Section header | 20-24pt bold |
| Body text | 14-16pt |
| Captions | 10-12pt muted |

### Spacing

- 0.5" minimum margins
- 0.3-0.5" between content blocks
- Leave breathing room — don't fill every inch

### Avoid (Common Mistakes)

- Don't repeat the same layout — vary columns, cards, and callouts across slides
- Don't center body text — left-align paragraphs and lists; center only titles
- Don't skimp on size contrast — titles need 36pt+ to stand out from 14-16pt body
- Don't default to blue — pick colors that reflect the specific topic
- Don't mix spacing randomly — choose 0.3" or 0.5" gaps and use consistently
- Don't style one slide and leave the rest plain — commit fully or keep it simple throughout
- Don't create text-only slides — add images, icons, charts, or visual elements
- Don't forget text box padding — when aligning lines or shapes with text edges, set `margin: 0` on the text box or offset the shape to account for padding
- Don't use low-contrast elements — icons AND text need strong contrast against the background
- NEVER use accent lines under titles — these are a hallmark of AI-generated slides; use whitespace or background color instead

---

## QA (Required)

**Assume there are problems. Your job is to find them.**

Your first render is almost never correct. Approach QA as a bug hunt, not a confirmation step.

### Content QA

```bash
python -m markitdown output.pptx
```

Check for missing content, typos, wrong order.

### Visual QA

Convert slides to images, then inspect for overlapping elements, text overflow, low-contrast text, uneven gaps, insufficient margins, leftover placeholder content.

### Verification Loop

1. Generate slides → Convert to images → Inspect
2. List issues found (if none found, look again more critically)
3. Fix issues
4. Re-verify affected slides — one fix often creates another problem
5. Repeat until a full pass reveals no new issues

---

## Converting to Images

```bash
soffice --headless --convert-to pdf /workspace/output.pptx --outdir /workspace/preview/
pdftoppm -jpeg -r 150 /workspace/preview/output.pdf /workspace/preview/slide
ls -1 /workspace/preview/slide-*.jpg
```

---

## Dependencies (pre-installed)

- `markitdown[pptx]` — text extraction from PPTX
- `pptxgenjs` — Node.js PPTX creation (npm)
- `python-pptx` — Python PPTX editing
- `Pillow` — image manipulation
- LibreOffice (`soffice`) — PDF conversion
- Poppler (`pdftoppm`) — PDF to images

---

## Template Mode

**Trigger**: A `.pptx` file exists in `/workspace/references/` (e.g. `template.pptx`).

When a template is provided, **skip pptxgenjs entirely**. The template defines the visual identity — your job is to select the right slide layouts and inject content pixel-perfectly. Use this workflow instead of the scratch workflow.

---

### Step 1 — Catalog the Template

Extract thumbnails for every template slide, then extract text schemas:

```bash
mkdir -p /workspace/template_preview
soffice --headless --convert-to pdf /workspace/references/template.pptx \
  --outdir /workspace/template_preview/
pdftoppm -jpeg -r 100 /workspace/template_preview/template.pdf \
  /workspace/template_preview/tpl
ls /workspace/template_preview/tpl-*.jpg
```

```python
# Run: python extract_schema.py
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
import json

prs = Presentation('/workspace/references/template.pptx')
catalog = []
for i, slide in enumerate(prs.slides):
    shapes = []
    for s in slide.shapes:
        info = {
            'name': s.name,
            'type': str(s.shape_type),
            'is_picture': s.shape_type == MSO_SHAPE_TYPE.PICTURE,
            'left_in': round(s.left / 914400, 2),
            'top_in': round(s.top / 914400, 2),
            'w_in': round(s.width / 914400, 2),
            'h_in': round(s.height / 914400, 2),
        }
        if s.has_text_frame:
            info['text'] = [p.text.strip() for p in s.text_frame.paragraphs if p.text.strip()]
        shapes.append(info)
    catalog.append({'slide_index': i, 'shapes': shapes})

print(json.dumps(catalog, indent=2))
```

**After running**: look at each `tpl-XX.jpg` image AND the schema output. Identify and name each slide type, e.g.:
- Slide 0: "Title" — large heading + subtitle
- Slide 1: "Section header" — bold section title, minimal content
- Slide 2: "Two-column content" — title + left/right body areas
- Slide 3: "Callout/highlight" — colored accent block + supporting text
- Slide 4: "Closing" — thank-you / contact / CTA

---

### Step 2 — Plan the Deck

Using the template catalog + the user's brief, produce a JSON plan. Write it to `/workspace/deck_plan.json`:

```json
[
  {
    "output_slide": 0, "template_slide": 0, "type": "Title",
    "content": { "title": "Course Title Here", "subtitle": "Tagline or audience" }
  },
  {
    "output_slide": 1, "template_slide": 2, "type": "Content",
    "content": {
      "title": "Module 1: Introduction",
      "sections": [
        { "heading": "What is X", "body": "Short explanation here." },
        { "heading": "Why it matters", "body": "Key reason here." }
      ]
    }
  },
  {
    "output_slide": 2, "template_slide": 3, "type": "Callout",
    "content": { "title": "Key Insight", "body": "One concise key point." }
  },
  {
    "output_slide": 3, "template_slide": 4, "type": "Closing",
    "content": { "title": "Thank You", "body": "Contact / next steps." }
  }
]
```

**Rules for planning:**
- Vary slide types — don't repeat the same layout back-to-back unless the template is single-layout
- Match content density to the template slide's capacity — don't plan 6 bullet points for a 2-point layout
- Callout/highlight slides = one sharp key point only, never the full body

---

### Step 3 — Build the Deck

Write and run `adapt_slides.py`:

```python
from pptx import Presentation
from pptx.util import Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE
import copy, json, shutil

TEMPLATE = '/workspace/references/template.pptx'
OUTPUT   = '/workspace/output.pptx'

with open('/workspace/deck_plan.json') as f:
    plan = json.load(f)

# ── helpers ───────────────────────────────────────────────────────────────

def set_shape_text(shape, new_text):
    """Replace text while preserving run formatting (color, bold, font family).
    Shrinks font 2 pt at a time if text is long; floor = 70% of original."""
    if not shape.has_text_frame:
        return
    tf = shape.text_frame
    first_para = tf.paragraphs[0]
    if not first_para.runs:
        return
    first_run = first_para.runs[0]
    orig_pt = (first_run.font.size.pt if first_run.font.size else None) or 18
    floor_pt = max(12, int(orig_pt * 0.70))
    # Set text on first run, clear the rest
    first_run.text = new_text
    for run in first_para.runs[1:]:
        run.text = ''
    for para in tf.paragraphs[1:]:
        for run in para.runs:
            run.text = ''
    # Shrink if needed (rough char-capacity estimate)
    est_cap = max(20, int(shape.width / 914400 * 10))
    current_pt = orig_pt
    while len(new_text) > est_cap * (orig_pt / current_pt) and current_pt > floor_pt:
        current_pt -= 2
    if current_pt < orig_pt:
        first_run.font.size = Pt(current_pt)

def is_callout(shape):
    """True if the shape has a colored (non-white) fill — treat as callout."""
    if not shape.has_text_frame:
        return False
    try:
        from pptx.dml.color import RGBColor
        fill = shape.fill
        if fill.type is not None:
            rgb = fill.fore_color.rgb
            return rgb not in (RGBColor(0xFF, 0xFF, 0xFF),)
    except Exception:
        pass
    return False

def inject_content(slide, content):
    """Map content dict onto slide shapes.
    NEVER modifies: pictures, colors, positions, sizes."""
    text_shapes = [
        s for s in slide.shapes
        if s.has_text_frame and s.shape_type != MSO_SHAPE_TYPE.PICTURE
    ]
    if not text_shapes:
        return

    # Sort top-to-bottom so title = topmost shape
    text_shapes.sort(key=lambda s: s.top)

    # Title = topmost + widest among first 3 shapes
    title_shape = max(text_shapes[:3], key=lambda s: s.width)

    if 'title' in content:
        set_shape_text(title_shape, content['title'])

    body_shapes = [s for s in text_shapes if s is not title_shape]
    callouts = [s for s in body_shapes if is_callout(s)]
    non_callouts = [s for s in body_shapes if not is_callout(s)]

    # Subtitle (title slides)
    if 'subtitle' in content and non_callouts:
        set_shape_text(non_callouts[0], content['subtitle'])

    # Sections → body text
    if 'sections' in content and non_callouts:
        body_text = '\n'.join(
            (f"{s['heading']}: {s['body']}" if s.get('heading') else s['body'])
            for s in content['sections']
        )
        set_shape_text(non_callouts[0], body_text)

    # Plain body
    if 'body' in content and non_callouts:
        set_shape_text(non_callouts[0], content['body'])

    # Callout shapes = one short key point
    if callouts:
        key_point = (
            content.get('callout') or
            content.get('body') or
            (content['sections'][0]['body'] if content.get('sections') else '')
        )
        if key_point:
            # Truncate to one sentence for callouts
            sentence = key_point.split('.')[0].strip() + '.'
            set_shape_text(callouts[0], sentence)
        else:
            set_shape_text(callouts[0], '')

# ── build deck ────────────────────────────────────────────────────────────

prs = Presentation(TEMPLATE)
n_template = len(prs.slides)

for item in plan:
    tpl_idx = item['template_slide']
    src = prs.slides[tpl_idx]

    # Add blank slide, replace its shape tree with a deep copy of the template slide
    new_slide = prs.slides.add_slide(prs.slide_layouts[6])  # layout 6 = blank
    sp_tree = new_slide.shapes._spTree
    for elem in list(sp_tree):
        sp_tree.remove(elem)
    for elem in src.shapes._spTree:
        sp_tree.append(copy.deepcopy(elem))

    # Re-register image relationships so pictures render
    for rel in src.part.rels.values():
        if 'image' in rel.reltype:
            try:
                new_slide.part.relate_to(rel.target_part, rel.reltype)
            except Exception:
                pass  # shared image already registered

    inject_content(new_slide, item['content'])

# Remove original template slides (they were only needed as sources)
sldIdLst = prs.slides._sldIdLst
for _ in range(n_template):
    sldIdLst.remove(sldIdLst[0])

prs.save(OUTPUT)
print(f'Saved — {len(plan)} slides → {OUTPUT}')
```

---

### Step 4 — Visual QA Loop (same as scratch mode)

```bash
mkdir -p /workspace/preview
soffice --headless --convert-to pdf /workspace/output.pptx --outdir /workspace/preview/
pdftoppm -jpeg -r 150 /workspace/preview/output.pdf /workspace/preview/slide
ls -1 /workspace/preview/slide-*.jpg
```

Inspect every slide. Assume there are problems:
- Stale template placeholder text still visible ("Enter text here", "Click to edit")
- Wrong shape populated (subtitle text in wrong box)
- Text overflow / cut off
- Callout shape showing full body instead of one key point
- Missing content (a section not injected because body_shapes was empty)

**Fix loop**: adjust `inject_content()` or the content in `deck_plan.json` → re-run `adapt_slides.py` → re-render → re-inspect. Repeat until all slides are clean.

---

### Pixel-Perfect Rules

| Rule | What it means |
|------|---------------|
| **Never change colors** | No `RGBColor`, fill colors, or theme colors — ever |
| **Never move or resize shapes** | `left`, `top`, `width`, `height` stay exactly as template |
| **Never touch pictures** | Skip all `MSO_SHAPE_TYPE.PICTURE` shapes |
| **Preserve run formatting** | Keep `bold`, `italic`, `font.name`, `color` from the original run |
| **Shrink font, don't overflow** | Reduce font 2 pt at a time; floor = 70% of original size |
| **Callouts = one key point** | Colored fill shapes get a single short sentence, never full body |
| **Clear all stale text** | Every placeholder must be replaced with real content or cleared to `''` |

---

## OfficePlane integration

When this skill runs inside OfficePlane:
- The agent has access to ECM tools through the SkillExecutor (Phase 7+ tool layer).
- Generated artifacts should be written under the workspace passed by the runner.
- Source content should cite the originating Document/Chapter/Section IDs in any output JSON.
