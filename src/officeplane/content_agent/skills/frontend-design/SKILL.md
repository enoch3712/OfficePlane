---
name: frontend-design
description: Create distinctive HTML slide presentations with reveal.js. Custom themes, Google Fonts, Playwright screenshots for verification.
---

# Frontend & HTML Slide Design Skill

You create distinctive, visually stunning HTML presentations and web interfaces.

## HTML Slide Frameworks

### reveal.js (recommended)

```bash
cd /workspace && mkdir slides && cd slides
npm init -y && npm install reveal.js
```

Features: fragments, speaker notes, auto-animate, Markdown slides, PDF export, vertical slides.

### Alternatives
- **Marp** — Markdown-based slides: `npm install @marp-team/marp-cli`
- **Slidev** — Vue-powered slides for developers
- **Custom HTML** — hand-crafted HTML/CSS/JS for full control

## Design Principles

- **Typography first** — load distinctive Google Fonts. Pair a bold display font with a clean body font.
- **Color palette** — choose 3-5 colors. One dominant, one accent, rest supporting.
- **Motion** — CSS transitions and reveal.js animations for engagement.
- **Whitespace** — generous margins and padding. Don't cram.
- **Contrast** — ensure text is readable. Dark on light OR light on dark, never muddy.

## NEVER do these
- Default reveal.js themes without customization
- Arial, Inter, or system fonts
- Purple gradient on white background
- More than 7 bullet points per slide
- Walls of text
- Low-contrast text on busy backgrounds

## Verification

After building HTML slides, ALWAYS screenshot them:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("file:///workspace/slides/index.html")

    # Screenshot each slide
    slides = page.query_selector_all(".reveal .slides > section")
    for i in range(len(slides)):
        page.evaluate(f"Reveal.slide({i})")
        page.wait_for_timeout(500)
        page.screenshot(path=f"/workspace/preview/slide-{i+1:02d}.png")

    browser.close()
```

Look at the screenshots. Fix anything that looks off — alignment, readability, spacing, colors.

---

## OfficePlane integration

When this skill runs inside OfficePlane:
- The agent has access to ECM tools through the SkillExecutor (Phase 7+ tool layer).
- Generated artifacts should be written under the workspace passed by the runner.
- Source content should cite the originating Document/Chapter/Section IDs in any output JSON.
