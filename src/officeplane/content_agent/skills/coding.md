# Coding Skill - Pre-installed Tools Reference

## System Tools

| Tool | Command | Purpose |
|------|---------|---------|
| Node.js 22 | `node` | JavaScript execution |
| pptxgenjs | `require("pptxgenjs")` | PPTX creation (global npm package) |
| Python 3 | `python3` | Python scripts |
| LibreOffice | `libreoffice --headless` | Document conversion |
| Chromium | Via Playwright | HTML rendering & screenshots |
| ImageMagick | `convert`, `magick` | Image processing |

## Node.js Patterns

### Write and execute script
```bash
cat > script.js << 'EOF'
// Your code here
EOF
node script.js
```

### Install additional npm packages (if needed)
```bash
npm install --save <package-name>
```

## Python Patterns

### matplotlib chart
```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(['A', 'B', 'C'], [10, 20, 30], color='#39FF14')
ax.set_facecolor('#0F172A')
fig.patch.set_facecolor('#0F172A')
ax.tick_params(colors='white')
plt.savefig('chart.png', dpi=150, bbox_inches='tight', facecolor='#0F172A')
```

### SVG to PNG
```python
import cairosvg
cairosvg.svg2png(url='input.svg', write_to='output.png', output_width=1920)
```

## File Operations
- All file operations are scoped to the workspace directory
- Use relative paths from the workspace root
- Primary output must be named `presentation.pptx` or `presentation.html`
- Always create `metadata.json` alongside the output

## metadata.json Format
```json
{
  "title": "Presentation Title",
  "slides": [
    { "title": "Slide 1 Title", "description": "Brief description" },
    { "title": "Slide 2 Title", "description": "Brief description" }
  ]
}
```
