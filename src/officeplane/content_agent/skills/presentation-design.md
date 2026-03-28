# Presentation Design Skill

## pptxgenjs Quick Reference

```javascript
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();

// Set layout
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 inches

// Define master slides
pres.defineSlideMaster({
  title: "TITLE_SLIDE",
  background: { color: "0F172A" },
  objects: [
    { text: { text: "", options: { x: 0.5, y: 2.5, w: 12, h: 1.5, fontSize: 36, color: "FFFFFF", fontFace: "Noto Sans", bold: true } } },
  ],
});

// Add slides
const slide = pres.addSlide();
slide.background = { color: "0F172A" };

// Text
slide.addText("Title", { x: 0.5, y: 0.5, w: 12, h: 1, fontSize: 28, color: "FFFFFF", fontFace: "Noto Sans", bold: true });

// Bullet points
slide.addText(
  [
    { text: "Point 1", options: { bullet: true, fontSize: 18, color: "E2E8F0" } },
    { text: "Point 2", options: { bullet: true, fontSize: 18, color: "E2E8F0" } },
  ],
  { x: 0.5, y: 1.5, w: 11, h: 4, fontFace: "Noto Sans", paraSpaceAfter: 8 }
);

// Shapes
slide.addShape(pres.ShapeType.rect, { x: 0.5, y: 6, w: 12, h: 0.1, fill: { color: "39FF14" } });

// Tables
const rows = [
  [{ text: "Header 1", options: { bold: true, fill: "1E293B", color: "FFFFFF" } }, { text: "Header 2", options: { bold: true, fill: "1E293B", color: "FFFFFF" } }],
  ["Cell 1", "Cell 2"],
];
slide.addTable(rows, { x: 0.5, y: 2, w: 12, colW: [6, 6], border: { color: "334155", pt: 1 } });

// Charts
slide.addChart(pres.charts.BAR, [{ name: "Series 1", labels: ["A", "B", "C"], values: [10, 20, 30] }], { x: 1, y: 1.5, w: 10, h: 5 });

// Save
pres.writeFile({ fileName: "presentation.pptx" });
```

## Professional Color Palettes

### Dark Corporate (Default)
- Background: `0F172A` (dark navy)
- Surface: `1E293B` (slate 800)
- Text primary: `FFFFFF`
- Text secondary: `94A3B8` (slate 400)
- Accent: `39FF14` (neon green - OfficePlane brand)
- Accent 2: `3B82F6` (blue)

### Light Professional
- Background: `FFFFFF`
- Surface: `F1F5F9` (slate 100)
- Text primary: `0F172A`
- Text secondary: `64748B`
- Accent: `2563EB` (blue 600)
- Accent 2: `059669` (emerald 600)

## Slide Structure Best Practices
1. **Title Slide**: Company/topic name, subtitle, date
2. **Agenda**: 3-5 key topics with brief descriptions
3. **Content Slides**: One idea per slide, 5-7 bullets max
4. **Data Slides**: One chart/table per slide, clear labels
5. **Summary**: Key takeaways, next steps
6. **Thank You/Q&A**: Contact info, resources

## Typography
- Titles: 28-36pt, bold
- Subtitles: 20-24pt, regular
- Body: 16-20pt, regular
- Captions: 12-14pt, italic
- Font families: Noto Sans (primary), Roboto, Open Sans
