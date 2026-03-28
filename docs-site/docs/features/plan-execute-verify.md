---
sidebar_position: 2
title: Plan, Execute, Verify
---

# Plan, Execute, Verify

OfficePlane's core editing workflow is a three-phase protocol. You describe what you want; an AI plans the changes, executes them atomically, then verifies the result matches your intent.

## The Protocol

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   1. Plan    │────>│  2. Execute  │────>│  3. Verify   │
│              │     │              │     │              │
│  Generate    │     │  Run action  │     │  AI checks   │
│  action tree │     │  tree with   │     │  result vs   │
│  from prompt │     │  dependency  │     │  original    │
│              │     │  resolution  │     │  intent      │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Phase 1: Plan

Given a natural language prompt and the current document structure, the planner generates an **action tree** — a dependency graph of atomic operations.

```bash
POST /api/documents/{id}/plan
{
  "prompt": "Add a new chapter about market analysis with sections for competitors, pricing, and market size"
}
```

### Action Types

| Action | Description |
|--------|-------------|
| `add_chapter` | Create a new chapter in the document |
| `add_section` | Add a section to a chapter |
| `write_page` | Create a new page with content |
| `edit_page` | Modify an existing page's content |
| `delete_page` | Remove a page |

### Action Tree Example

```json
{
  "actions": [
    {
      "node_id": "node_0",
      "action": "add_chapter",
      "params": { "title": "Market Analysis", "order_index": 3 },
      "depends_on": []
    },
    {
      "node_id": "node_1",
      "action": "add_section",
      "params": { "title": "Competitors", "chapter_id": "$node_0.id" },
      "depends_on": ["node_0"]
    },
    {
      "node_id": "node_2",
      "action": "write_page",
      "params": { "section_id": "$node_1.id", "content": "..." },
      "depends_on": ["node_1"]
    }
  ]
}
```

### Dependency Resolution

Actions reference each other using the **placeholder format** `$node_N.id`. The executor resolves these at runtime:

1. Topological sort by `depends_on`
2. Execute in order
3. Replace `$node_N.id` with actual IDs from previous results

## Phase 2: Execute

The plan executor runs the action tree atomically — all-or-nothing.

```bash
POST /api/documents/{id}/execute
{
  "actions": [ ... ]  // The action tree from Phase 1
}
```

### Atomicity

- Actions execute in topological order
- If any action fails, all previous changes are rolled back
- The document is never left in a partial state
- The executor holds the document lock for the entire operation

### Execution Flow

```
Action Tree
├── node_0: add_chapter("Market Analysis")
│   └── Returns: chapter_id = "ch-456"
├── node_1: add_section("Competitors", chapter_id="ch-456")
│   └── Returns: section_id = "sec-789"
├── node_2: write_page(section_id="sec-789", content="...")
│   └── Returns: page_id = "pg-012"
└── All succeeded → COMMIT
```

## Phase 3: Verify

After execution, an AI verification step checks whether the changes actually match the original intent.

```bash
POST /api/documents/{id}/verify
{
  "original_request": "Add a new chapter about market analysis..."
}
```

The verifier:
1. Loads the updated document structure
2. Compares it against the original request
3. Returns a verification report with confidence score

```json
{
  "verified": true,
  "confidence": 0.95,
  "report": "The document now contains a Market Analysis chapter with three sections: Competitors, Pricing, and Market Size. All sections contain relevant content matching the request."
}
```

## End-to-End Example

```bash
# 1. Plan
curl -X POST http://localhost:8001/api/documents/abc/plan \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Add an executive summary at the beginning"}'

# 2. Review the plan (optional — displayed in the UI)

# 3. Execute
curl -X POST http://localhost:8001/api/documents/abc/execute \
  -H "Content-Type: application/json" \
  -d '{"actions": [...]}'

# 4. Verify
curl -X POST http://localhost:8001/api/documents/abc/verify \
  -H "Content-Type: application/json" \
  -d '{"original_request": "Add an executive summary at the beginning"}'
```
