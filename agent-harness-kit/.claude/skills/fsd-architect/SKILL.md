---
name: fsd-architect
description: Design and structure React applications using Feature-Sliced Design (FSD). Enforces strict unidirectional data flow, layer isolation, and business-value slicing.
compatibility: React 18/19, TypeScript, Tailwind CSS.
---

# Feature-Sliced Design (FSD) Architect

## When to use this skill

Use this skill when initializing a new React project, refactoring a "spaghetti code" frontend, or adding complex features. It is strictly for **React** applications using the 2025 modern stack (React Compiler, Zustand, TanStack Query).

## 1. Core Philosophy

FSD prevents coupling by organizing code into **Business Value Slices** rather than technical layers (controllers/views).

- **Unidirectional Flow:** A layer can *only* import from layers strictly below it.
- **Public API:** Every slice must have an `index.ts`. External code must *only* import from this file, never from internal segments.

## 2. The Layer Hierarchy (Top to Bottom)

1. **`app`** (The Glue)
   - *Role:* Global initialization, providers, styles, router.
   - *Allowed Imports:* Pages, Widgets, Features, Entities, Shared.
2. **`pages`** (Composition)
   - *Role:* Assemble widgets into a full route (e.g., `CheckoutPage`).
   - *Allowed Imports:* Widgets, Features, Entities, Shared.
3. **`widgets`** (Standalone UI)
   - *Role:* Large, independent UI blocks (e.g., `Header`, `Feed`, `Sidebar`).
   - *Allowed Imports:* Features, Entities, Shared.
4. **`features`** (User Interactions / Verbs)
   - *Role:* Handles user actions that bring value (e.g., `AuthByPhone`, `AddToCart`, `LikePost`).
   - *Allowed Imports:* Entities, Shared.
   - *Constraint:* A Feature cannot import another Feature.
5. **`entities`** (Business Data / Nouns)
   - *Role:* Models domain objects (e.g., `User`, `Product`, `Order`).
   - *Allowed Imports:* Shared.
   - *Constraint:* An Entity cannot import another Entity.
6. **`shared`** (Infrastructure)
   - *Role:* Reusable, domain-agnostic code (UI Kit, API client, libs).
   - *Allowed Imports:* None.

## 3. Slice Anatomy

Inside a layer (e.g., `entities/user`), organize by **Segments**:

```text
src/entities/user/
├── ui/           # Components (UserAvatar, UserCard)
├── model/        # State (Zustand stores, types)
├── api/          # Data fetching (TanStack Query)
├── lib/          # Helpers specific to this slice
└── index.ts      # PUBLIC API (The only entry point)
```

## 4. Modern Stack Integration (2025 Standards)

### React Compiler (React 19)

- **No Manual Memoization:** Do NOT wrap `shared/ui` atoms in `memo`. The compiler handles stability.
- **Clean Models:** Write business logic functions in `model` without `useCallback`.

### State Management

- **Server State:** Use **TanStack Query** in `api` segments.
- **Client State:** Use **Zustand** in `model` segments.
- **Anti-Pattern:** Do NOT create a single global `store.ts`. Split stores by slice (e.g., `useAuthStore` inside `features/auth`).

### Styling (Tailwind)

- **Shared UI:** Build your design system in `shared/ui` using Tailwind (or libraries like `shadcn/ui`).
- **Feature UI:** Use utility classes directly. Avoid CSS Modules unless strictly necessary for complex animations.

## 5. Validation

Use **Steiger** to lint the architecture. It detects strictly forbidden circular dependencies and cross-imports (e.g., Feature A importing Feature B).
