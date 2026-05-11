---
name: vector-search
description: Semantic search across ingested documents. Returns top-k passages.
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: query
    type: str
    required: true
  - name: document_ids
    type: list[str]
    required: false
  - name: collection_id
    type: str
    required: false
  - name: limit
    type: int
    required: false
outputs:
  - name: count
    type: int
  - name: results
    type: list[dict]
---
