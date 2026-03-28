# FSD Import Rules

The arrow (`↓`) indicates allowed import direction.

```text
Layer        Can Import From
-------------------------------------------------------
1. app       ↓ pages, widgets, features, entities, shared
2. pages     ↓ widgets, features, entities, shared
3. widgets   ↓ features, entities, shared
4. features  ↓ entities, shared
5. entities  ↓ shared
6. shared    (No imports allowed)
```

## Common Mistakes

1. **Cross-Importing:**
   - ❌ `import { Product } from 'entities/product'` inside `entities/user`
   - ✅ Move shared logic to `shared` or compose them in a `widget`.

2. **Deep Imports:**
   - ❌ `import { Button } from 'shared/ui/Button/Button'`
   - ✅ `import { Button } from 'shared/ui'`

3. **God-Mode Features:**
   - ❌ Creating a `features/shop` that does everything.
   - ✅ Split into `features/add-to-cart`, `features/product-filter`, `entities/product`.
