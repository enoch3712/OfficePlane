---
name: frontend
description: Frontend Engineering — OfficePlane Design System. Use when building, modifying, or reviewing UI components, pages, or styles in the ui/ directory.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, Agent
---

# Frontend Engineering — OfficePlane Design System

You are building UI for OfficePlane, an agentic document management platform. OfficePlane's frontend is a **dark, high-contrast instrument panel** — it feels like mission control for document intelligence. Every component embodies the design system: **Phosphor Green as the signal, Warm Orange as the accent, dark navy as the void, and typography as hierarchy**. Read this spec in full before starting work.

## The Palette

```
VOID       #070D1F  hsl(223 54% 5%)    — background, the deep navy
SURFACE    #0A1020  hsl(220 40% 7%)    — cards, popovers, elevated surfaces
FOREGROUND #DDE6F0  hsl(210 40% 92%)   — primary text, near-white
```

### Primary — Phosphor Green

The signature color. Neon, electric, unmistakable.

```
50:  #f0fff0    100: #ccffcc    200: #99ff99
300: #66ff55    400: #39ff14 ← DEFAULT    500: #30e010
600: #28c00e    700: #1f9a0b    800: #167508    900: #0d5005
```

CSS variable: `--primary: 110 100% 54%`
Usage: buttons, active states, focus rings, glow effects, status "connected", scrollbar thumbs.

### Accent — Warm Orange

The counterpoint. Used for secondary emphasis and visual warmth.

```
DEFAULT: #F97316  hsl(24 95% 53%)
```

CSS variable: `--accent: 24 95% 53%`
Usage: secondary badges, sparkle icons, gradient endpoints, chart color 2.

### Semantic Colors

These are used for **status badges and feedback only** — never as decorative colors.

```
SUCCESS      #22C55E  hsl(142 76% 46%)  — completed, uploaded, healthy
WARNING      #F59E0B  hsl(38 92% 50%)   — queued, connecting, caution
DESTRUCTIVE  #EF4444  hsl(0 84% 60%)    — failed, error, danger
INFO         blue-400                     — running, informational
```

### Depth & Surface Hierarchy

```
background:  hsl(223 54% 5%)   — page background (#070D1F)
card:        hsl(220 40% 7%)   — cards, popovers (#0A1020)
secondary:   hsl(220 20% 12%)  — muted backgrounds, hover states
muted:       hsl(220 20% 12%)  — disabled backgrounds
border:      hsl(220 20% 15%)  — borders, dividers
```

In practice, also use `white/[0.03]` for subtle input backgrounds and `white/10` for borders over dark surfaces.

### Text Hierarchy

```
foreground:       hsl(210 40% 92%)  — primary text, headings (#DDE6F0)
muted-foreground: hsl(215 16% 55%) — labels, timestamps, secondary text
slate-500:        — placeholder text, disabled labels
slate-400:        — descriptions, toast subtitles
white:            — high-emphasis text on colored or dark surfaces
```

## Typography: Two Fonts, Two Voices

| Font | CSS Variable | Role | When to use |
|------|-------------|------|-------------|
| **Space Grotesk** (500-700) | `--font-heading` | Structural voice | Page titles, section headings, brand text |
| **IBM Plex Sans** (400-700) | `--font-body` | Functional voice | Body text, descriptions, UI labels, buttons |
| **JetBrains Mono** (400-600) | `--font-mono` | Code voice | Code snippets, technical data, monospace displays |

### Usage

```css
/* Headings automatically use Space Grotesk via globals.css */
h1, h2, h3, h4, h5, h6 { font-family: var(--font-heading); }

/* Body text uses IBM Plex Sans */
body { font-family: var(--font-body); }

/* Force heading font in non-heading elements */
.font-heading { font-family: var(--font-heading); }
```

### Scale (Tailwind defaults)

```
text-xs   (12px)  — badges, timestamps, metadata
text-sm   (14px)  — body text, descriptions, labels
text-base (16px)  — primary content
text-lg   (18px)  — section headings, dialog titles
text-xl   (20px)  — page subtitles
text-2xl  (24px)  — page titles, brand text
```

## shadcn/ui Components

OfficePlane uses **shadcn/ui** with Radix UI primitives. All CSS variables follow the shadcn convention: `hsl(var(--token))`.

### Installed Components

| Component | Path | Notes |
|-----------|------|-------|
| **Button** | `@/components/ui/button` | 6 variants: default, destructive, outline, secondary, ghost, link. 4 sizes: default, sm, lg, icon |
| **Card** | `@/components/ui/card` | Card (with title, subtitle, accent left-border, actions), CardStats, StatItem |
| **Badge** | `@/components/ui/badge` | 6 variants: neutral, accent, warning, error, info, success. Mono uppercase tracked |
| **PageHeader** | `@/components/ui/page-header` | Breadcrumbs + title + subtitle + status + actions |
| **StatusIndicator** | `@/components/ui/status-indicator` | Symbol-based: active (pulse), completed, error, pending, warning |
| **EmptyState** | `@/components/ui/empty-state` | Centered empty state with icon and message |
| **LoadingState** | `@/components/ui/loading-state` | Animated skeleton placeholder |
| **Toast** | `@/components/ui/toast` | Custom context-based provider. Types: success, error, info, document |
| **Dialog** | via `@radix-ui/react-dialog` | Radix primitive available, custom dialogs built on top |

### Adding New shadcn Components

When adding new UI primitives, use the shadcn/ui pattern:
1. Place in `ui/components/ui/`
2. Use `class-variance-authority` (cva) for variants
3. Use `cn()` from `@/lib/cn` for class merging (clsx + tailwind-merge)
4. Forward refs, accept className prop
5. Use CSS variables from globals.css — never hardcode colors

### Button Variants

```tsx
import { Button } from '@/components/ui/button'

<Button>Primary Action</Button>                    // phosphor green bg
<Button variant="destructive">Delete</Button>      // red bg
<Button variant="outline">Cancel</Button>          // bordered, transparent
<Button variant="secondary">Secondary</Button>     // muted bg
<Button variant="ghost">Subtle</Button>            // no bg, hover only
<Button variant="link">Link</Button>               // underline on hover
```

Primary buttons get a glow effect:
```tsx
<Button className="shadow-lg shadow-primary/20 hover:shadow-xl hover:shadow-primary/30">
```

## Component Patterns

### Cards

Standard card pattern — dark surface with subtle border:
```tsx
<div className="bg-card border border-border rounded-lg p-6">
  <h3 className="text-lg font-semibold text-foreground">Title</h3>
  <p className="text-sm text-muted-foreground mt-1">Description</p>
</div>
```

For inline dark cards (e.g., sidebar, dialogs), use raw values:
```tsx
<div className="bg-[#060a14] border border-white/10 rounded-xl">
```

### Badges

Status badges use colored backgrounds at low opacity:
```css
.badge          { @apply inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium; }
.badge-queued   { @apply bg-amber-500/15 text-amber-400; }
.badge-running  { @apply bg-blue-500/15 text-blue-400; }
.badge-completed{ @apply bg-green-500/15 text-green-400; }
.badge-failed   { @apply bg-red-500/15 text-red-400; }
.badge-open     { @apply bg-emerald-500/15 text-emerald-400; }
```

For accent badges: `bg-[#39ff14]/10 text-[#39ff14]`
For orange badges: `bg-accent/15 text-accent`

### Dialogs / Modals

Custom dialog pattern (over Radix or manual):
```tsx
{/* Backdrop */}
<div className="absolute inset-0 bg-black/45 animate-in fade-in-0 duration-150" />

{/* Dialog */}
<div className="bg-[#060a14] border border-white/10 rounded-xl shadow-xl
                animate-in fade-in-0 zoom-in-95 duration-150">
  {/* Content with p-6 */}
</div>
```

### Inputs

```tsx
<input className="w-full px-3 py-2 text-sm bg-white/[0.03] border border-white/10 rounded-lg
                  text-slate-200 placeholder-slate-500
                  focus:outline-none focus:ring-1 focus:ring-[#39ff14]/30 focus:border-[#39ff14]/50" />
```

### Navigation (Sidebar)

```tsx
// Active item
<Link className="bg-[#39ff14]/10 text-[#39ff14] border-r-2 border-[#39ff14]" />

// Inactive item
<Link className="text-slate-400 hover:bg-white/[0.03] hover:text-slate-200" />
```

Sidebar: `w-64` expanded, `w-16` collapsed, with `transition-all duration-300`.

### Status Indicators

Connection status uses a colored dot with pulse:
```tsx
<div className={`w-2.5 h-2.5 rounded-full ${
  status === 'connected' ? 'bg-success animate-pulse' :
  status === 'connecting' ? 'bg-warning' :
  status === 'error' ? 'bg-destructive' :
  'bg-muted-foreground'
}`} />
```

## Glow Effects

The phosphor green glow is the signature visual motif:

```css
.glow        { box-shadow: 0 0 20px hsl(var(--primary) / 0.15); }
.glow-accent { box-shadow: 0 0 20px hsl(var(--accent) / 0.15); }
```

Buttons, active panels, and hero elements use glow:
```tsx
className="shadow-lg shadow-primary/20 hover:shadow-xl hover:shadow-primary/30"
```

Gradient glow behind icons:
```tsx
<div className="absolute inset-0 bg-gradient-to-br from-primary to-accent blur-xl opacity-20 rounded-full" />
```

## Gradients

The primary-to-accent gradient is used for brand elements:
```tsx
// Text gradient
<h1 className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">

// Background gradient
<div className="bg-gradient-to-br from-primary to-accent p-2 rounded-xl">
```

## Animations

Uses `tailwindcss-animate` plugin. Available utilities:

```
animate-in          — entrance animation base
fade-in-0           — fade from transparent
zoom-in-95          — scale from 95%
slide-in-from-right-full — slide from right edge
animate-pulse       — built-in Tailwind pulse
animate-spin        — spinner rotation
accordion-down/up   — Radix accordion expand/collapse (200ms ease-out)
```

All custom transitions: `transition-colors`, `transition-all duration-200` or `duration-300`.

## Scrollbar

Custom phosphor-green-tinted scrollbar:
```css
scrollbar-width: thin;
scrollbar-color: hsl(var(--primary) / 0.3) transparent;
```

Apply with the `scrollbar-thin` utility class.

## Icons

Use **Lucide React** (`lucide-react`) for all icons. Standard size: `w-4 h-4` for inline, `w-5 h-5` for standalone, `w-6 h-6` for hero/header.

Key icons in use:
```
LayoutDashboard  FileText  Sparkles  Users  MessageSquare
Layers  Clock  Activity  Settings  Braces  Plus  X
ChevronLeft  ChevronRight  Loader2  AlertTriangle
CheckCircle2  AlertCircle  Info  Search
```

## Architecture

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 15.1 (App Router) |
| React | 19.0 |
| Styling | Tailwind CSS 3.4 + tailwindcss-animate |
| UI Primitives | shadcn/ui + Radix UI |
| State (client) | Zustand 5.0 |
| State (server) | TanStack React Query 5.56 |
| Real-time | WebSocket + Server-Sent Events |
| Icons | Lucide React |
| Utilities | clsx, tailwind-merge, class-variance-authority, date-fns |

### Directory Structure

```
ui/
├── app/
│   ├── globals.css          — CSS variables, base styles, utilities
│   ├── layout.tsx           — Root layout (next/font, Metadata, Providers)
│   ├── page.tsx             — Root redirect → /overview
│   ├── providers.tsx        — QueryClient + Toast providers
│   └── (dashboard)/         — Dashboard route group
│       ├── layout.tsx       — Sidebar + Header wrapper
│       ├── overview/        — Dashboard home
│       ├── documents/       — Document management
│       ├── generate/        — Document generation
│       ├── teams/           — Team collaboration
│       ├── chat/            — Agentic chat
│       ├── instances/       — Running instances
│       ├── tasks/           — Task queue
│       ├── activity/        — Activity log
│       └── settings/        — Settings
├── components/
│   ├── ui/                  — shadcn/ui primitives (Button, Toast)
│   ├── Sidebar.tsx          — Collapsible navigation
│   ├── Header.tsx           — Top bar with status + actions
│   ├── AgenticChat.tsx      — Main chat interface
│   ├── ConfirmDialog.tsx    — Reusable confirmation dialog
│   ├── DocumentsPanel.tsx   — Document list
│   ├── DocumentStructure.tsx — Document tree/structure view
│   ├── FileUploadDialog.tsx — File upload with drag-and-drop
│   ├── HistoryPanel.tsx     — Execution history view
│   ├── InstancesPanel.tsx   — Running instances panel
│   ├── MetricsPanel.tsx     — System metrics display
│   ├── PlanningChat.tsx     — Planning-mode chat
│   ├── TaskQueuePanel.tsx   — Task queue view
│   └── TimeAgo.tsx          — Relative time display
├── hooks/
│   ├── useWebSocket.ts      — WebSocket with auto-reconnect
│   └── useSSE.ts            — Server-Sent Events streaming
├── lib/
│   ├── cn.ts                — clsx + tailwind-merge helper
│   ├── types.ts             — TypeScript domain types
│   └── api.ts               — Typed API client
└── public/                  — Static assets
```

### Key Conventions

- **Server components by default.** Only add `'use client'` when you need state, event handlers, or browser APIs.
- **`cn()` for all className composition.** Import from `@/lib/cn`.
- **CSS variables for theming.** Always use `hsl(var(--token))` in globals.css, Tailwind classes everywhere else.
- **Path alias `@/*`** maps to `ui/` root.
- **React Query** for server state. 5s stale time, 10s refetch interval for dashboard data.
- **Zustand** for client state (UI state, selections, ephemeral state).

## Before Writing Code

1. Read this spec for the design system
2. Check existing components in `ui/components/ui/` — reuse before creating
3. Check `ui/components/` for existing custom components
4. Use CSS variables and Tailwind token classes — never hardcode hex colors in new components (existing `#39ff14` / `#060a14` hardcodes in older components are acceptable but prefer tokens for new work)
5. Use `cn()` for all class composition
6. Install new shadcn/ui components into `ui/components/ui/` following the established pattern

## Anti-Patterns (DO NOT)

- Do NOT introduce colors outside the palette — no random blues, purples, or grays not derived from the theme
- Do NOT use shadows for depth — use background color changes and borders (glow effects are the exception)
- Do NOT create components without accepting `className` prop
- Do NOT hardcode API URLs — use the existing `api.ts` client or environment variables
- Do NOT use `useEffect` for data fetching — use React Query
- Do NOT use Context for state that should be in Zustand
- Do NOT skip the `cn()` utility for conditional classes — no manual string concatenation
- Do NOT add heavy animation libraries — use `tailwindcss-animate` utilities and CSS transitions
- Do NOT break the dark theme — every surface must be dark, every text must be light
