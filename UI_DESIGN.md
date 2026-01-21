# OfficePlane UI Design System

## 🎨 Color Palette

We've implemented a beautiful, modern color palette inspired by Supabase with purple and teal accents:

### Light Mode
- **Primary**: Deep Purple/Indigo (#7C3AED) - Main brand color
- **Accent**: Bright Teal/Cyan (#06B6D4) - Highlights and CTAs
- **Success**: Emerald Green (#059669) - Success states
- **Warning**: Amber (#F59E0B) - Warning states
- **Destructive**: Rose Red (#EF4444) - Error states
- **Background**: Clean White with subtle gradient
- **Foreground**: Dark gray for text

### Dark Mode Support
The theme automatically adapts to dark mode with adjusted colors for better contrast and readability.

## 🧩 Components

### Button
Fully customizable button component with multiple variants:
- `default`: Primary purple background
- `destructive`: Red for dangerous actions
- `outline`: Border only
- `secondary`: Subtle background
- `ghost`: No background
- `link`: Text link style

Sizes: `default`, `sm`, `lg`, `icon`

### File Upload Dialog
Beautiful drag-and-drop file upload dialog with:
- ✅ Drag and drop support
- ✅ File type validation (.doc, .docx)
- ✅ File size display
- ✅ Smooth animations
- ⏳ Excel (.xls, .xlsx) - Coming Soon
- ⏳ PowerPoint (.pptx) - Coming Soon

## 🎯 Key Features

### 1. Gradient Logo
The OfficePlane logo features a beautiful gradient from primary to accent color with a subtle glow effect.

### 2. "Open Instance" Button
Located in the top-right header, clicking this button opens a file upload dialog where you can:
1. Drag & drop a Word document
2. Or click "browse files" to select one
3. See file preview before uploading
4. Upload only .DOC and .DOCX files (for now)

### 3. Live Connection Status
Real-time WebSocket connection indicator showing:
- 🟢 **Live**: Connected and receiving updates
- 🟡 **Connecting**: Establishing connection
- ⚫ **Disconnected**: No connection
- 🔴 **Error**: Connection error

### 4. Glassmorphism Effects
Modern glassmorphism effects with backdrop blur on the header for a premium feel.

### 5. Smooth Animations
- Button hover effects with shadow changes
- Dialog fade-in/zoom animations
- Gradient animations on logo
- Pulse effects on connection status

## 🛠 Customization

### Changing Colors
Edit `ui/app/globals.css` to customize the theme:

```css
:root {
  --primary: 263 70% 50%;      /* Change hue for different primary color */
  --accent: 189 94% 43%;        /* Change hue for different accent color */
  --success: 142 76% 36%;       /* Success color */
  --warning: 38 92% 50%;        /* Warning color */
  --destructive: 0 84.2% 60.2%; /* Error color */
}
```

### Theme Variables
All colors use CSS variables following the HSL format:
- Hue (0-360)
- Saturation (0-100%)
- Lightness (0-100%)

This makes it easy to adjust colors while maintaining consistency.

## 📐 Layout

### Max Width
Content is constrained to `1800px` for optimal readability on large screens.

### Spacing
Consistent spacing using Tailwind's spacing scale:
- Padding: `p-6` (24px)
- Gaps: `gap-6` (24px)
- Margins: `space-y-6` (24px vertical)

### Grid System
- Desktop: 2-column grid for main panels
- Mobile: Single column, stacks vertically

## 🎬 Animations

### Keyframes
- `gradient-shift`: Animated gradient backgrounds
- `accordion-down/up`: Smooth accordion transitions

### Utilities
- `.glow`: Primary color glow effect
- `.glow-accent`: Accent color glow effect
- `.gradient-border`: Animated gradient border
- `.scrollbar-thin`: Custom styled scrollbar

## 🚀 Usage Example

```tsx
import { Button } from '@/components/ui/button'

// Primary button
<Button>Click Me</Button>

// Accent button
<Button variant="outline">Secondary Action</Button>

// With icon
<Button className="gap-2">
  <Plus className="w-4 h-4" />
  Add Item
</Button>
```

## 📱 Responsive Design

The UI is fully responsive and optimized for:
- 📱 Mobile (320px+)
- 📱 Tablet (768px+)
- 💻 Desktop (1024px+)
- 🖥️ Large Desktop (1800px+)

## 🎨 Design Philosophy

### Inspiration
- **Supabase**: Clean, modern developer tools UI
- **Vercel**: Minimalist with powerful functionality
- **Linear**: Fast, keyboard-first interactions

### Principles
1. **Clarity**: Every element has a clear purpose
2. **Consistency**: Reusable components with variants
3. **Performance**: Lightweight, fast-loading
4. **Accessibility**: Proper contrast, keyboard navigation
5. **Delight**: Subtle animations and interactions

## 🔮 Future Enhancements

- [ ] Dark mode toggle
- [ ] Customizable theme picker
- [ ] More file type support (Excel, PowerPoint)
- [ ] Keyboard shortcuts
- [ ] Command palette (Cmd+K)
- [ ] Drag and drop for panels
- [ ] Real-time collaboration indicators
