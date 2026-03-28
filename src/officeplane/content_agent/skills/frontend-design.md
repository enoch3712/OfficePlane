# Frontend Design Skill

## HTML Presentation (Standalone)

For HTML-based presentations, create a single self-contained HTML file.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Presentation</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Noto Sans', sans-serif; background: #0F172A; color: #FFFFFF; }
    .slide {
      width: 100vw; height: 100vh; display: flex; flex-direction: column;
      justify-content: center; padding: 5vw; scroll-snap-align: start;
    }
    .slide h1 { font-size: 3rem; margin-bottom: 1rem; }
    .slide h2 { font-size: 2rem; color: #94A3B8; margin-bottom: 2rem; }
    .slide ul { font-size: 1.5rem; line-height: 2; list-style: none; }
    .slide ul li::before { content: "→ "; color: #39FF14; }
    .container { scroll-snap-type: y mandatory; overflow-y: scroll; height: 100vh; }
  </style>
</head>
<body>
  <div class="container">
    <div class="slide">
      <h1>Title Here</h1>
      <h2>Subtitle</h2>
    </div>
    <!-- More slides -->
  </div>
</body>
</html>
```

## Screenshot with Playwright

```javascript
const { chromium } = require('playwright');

async function captureSlides() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('file:///path/to/presentation.html');

  // Capture each slide
  const slides = await page.$$('.slide');
  for (let i = 0; i < slides.length; i++) {
    await slides[i].screenshot({ path: `slide-${i + 1}.png` });
  }
  await browser.close();
}
captureSlides();
```
