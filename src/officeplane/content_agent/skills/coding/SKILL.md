---
name: coding
description: Linux environment reference — pre-installed tools (LibreOffice, Chromium, Node.js, pptxgenjs, python-pptx, matplotlib), useful commands, and packaging workflow.
---

# Coding & Environment Skill

You have a fully equipped Linux container with these tools pre-installed:

## Pre-installed Python Libraries

- **python-pptx** — PowerPoint creation and editing
- **matplotlib** — charts, plots, diagrams
- **Pillow** — image manipulation
- **cairosvg** / **svglib** — SVG rendering
- **reportlab** — PDF generation
- **pandas** / **openpyxl** — data processing and Excel reading
- **jinja2** — HTML templating
- **playwright** — headless browser automation + screenshots

## Pre-installed System Tools

- **LibreOffice Impress** — `libreoffice --headless` for PPTX ↔ PDF/PNG conversion
- **Chromium** — headless browser for HTML rendering
- **ImageMagick** — `convert`, `montage` for image processing
- **Node.js 22** + npm — for reveal.js and other JS tools
- **zip/unzip** — packaging results
- **curl/wget** — downloading resources
- **git** — version control

## Installed Fonts

Liberation, DejaVu, Noto, Roboto, Open Sans, Lato — available system-wide.
For Google Fonts in HTML, use `<link>` tags.

## Useful Commands

```bash
# Convert PPTX to individual slide PNGs
libreoffice --headless --convert-to png --outdir /workspace/preview/ file.pptx

# Convert PPTX to PDF
libreoffice --headless --convert-to pdf --outdir /workspace/preview/ file.pptx

# Take screenshot of HTML page
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('file:///workspace/slides/index.html')
    page.screenshot(path='/workspace/preview/screenshot.png')
    b.close()
"

# Create image montage (all slides on one page)
montage /workspace/preview/slide-*.png -geometry 400x225+10+10 -tile 3x /workspace/preview/overview.png

# Install additional Python packages
uv pip install <package>

# Install additional npm packages
npm install <package>
```

## python-pptx Patterns (Template Mode)

### Extract all text from a slide

```python
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

prs = Presentation('template.pptx')
for i, slide in enumerate(prs.slides):
    print(f'--- Slide {i} ---')
    for s in slide.shapes:
        if s.has_text_frame:
            for para in s.text_frame.paragraphs:
                if para.text.strip():
                    print(f'  [{s.name}] {para.text.strip()}')
```

### Replace text, preserve formatting

```python
def set_shape_text(shape, new_text):
    """Set text on a shape, preserving run-level formatting (color, bold, font)."""
    if not shape.has_text_frame:
        return
    first_para = shape.text_frame.paragraphs[0]
    if not first_para.runs:
        return
    first_run = first_para.runs[0]
    first_run.text = new_text
    for run in first_para.runs[1:]:
        run.text = ''
    for para in shape.text_frame.paragraphs[1:]:
        for run in para.runs:
            run.text = ''
```

### Copy a template slide into the same presentation

```python
from pptx import Presentation
import copy

prs = Presentation('template.pptx')
src = prs.slides[2]  # template slide to copy

new_slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
sp_tree = new_slide.shapes._spTree
for elem in list(sp_tree):
    sp_tree.remove(elem)
for elem in src.shapes._spTree:
    sp_tree.append(copy.deepcopy(elem))

# Re-register image relationships
for rel in src.part.rels.values():
    if 'image' in rel.reltype:
        try:
            new_slide.part.relate_to(rel.target_part, rel.reltype)
        except Exception:
            pass
```

### Delete a slide by index

```python
sldIdLst = prs.slides._sldIdLst
sldIdLst.remove(sldIdLst[index])  # removes slide at position `index`
```

### Font auto-shrink

```python
from pptx.util import Pt

def shrink_to_fit(shape, new_text, min_pt=12):
    tf = shape.text_frame
    run = tf.paragraphs[0].runs[0] if tf.paragraphs[0].runs else None
    if not run:
        return
    orig_pt = (run.font.size.pt if run.font.size else None) or 18
    floor_pt = max(min_pt, int(orig_pt * 0.70))
    run.text = new_text
    est_cap = max(20, int(shape.width / 914400 * 10))
    current_pt = orig_pt
    while len(new_text) > est_cap * (orig_pt / current_pt) and current_pt > floor_pt:
        current_pt -= 2
    if current_pt < orig_pt:
        run.font.size = Pt(current_pt)
```

---

## Rules

- Always work inside `/workspace/`
- You have root access — install anything you need
- ALWAYS verify your work before packaging
- ALWAYS end by creating `/workspace/results.zip`

---

## OfficePlane integration

When this skill runs inside OfficePlane:
- The agent has access to ECM tools through the SkillExecutor (Phase 7+ tool layer).
- Generated artifacts should be written under the workspace passed by the runner.
- Source content should cite the originating Document/Chapter/Section IDs in any output JSON.
