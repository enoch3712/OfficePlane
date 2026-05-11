---
name: auto-categorize
description: Suggest which existing Collection an ingested document belongs to, and propose a new Collection name if none fit
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: document_id
    type: str
    required: true
    description: Prisma Document.id to classify
  - name: max_suggestions
    type: int
    required: false
    description: Max number of existing-collection suggestions (default 3)
outputs:
  - name: document_id
    type: str
  - name: suggested_collections
    type: list[dict]
    description: list of {collection_id, name, score, reason}
  - name: new_collection_proposal
    type: dict
    description: "{name, description, reason} — proposed if no existing collection scores well"
  - name: model
    type: str
---

# auto-categorize skill

This skill classifies a freshly-ingested document against all existing Collections in the workspace and returns ranked suggestions.

## How it works

1. **Build the target document signature** — fetch `summary`, `title`, and `topics` fields from the `Document` row and join them into a single text blob.

2. **Build collection signatures** — for every `Collection` row, concatenate the collection's `name`, `description`, and the summaries/topics of up to 5 of its member documents.

3. **Score by similarity** — compute Jaccard similarity between word sets of the target blob and each collection blob. This is a lightweight, deterministic heuristic that does not require an embedding server. If Phase 14's `/api/search/semantic` endpoint is available, callers can swap to embedding cosine-similarity instead.

4. **Return top-N suggestions** — sort collections by descending score and return the top `max_suggestions` entries with `{collection_id, name, score, reason}`.

5. **Propose a new collection if needed** — if the best Jaccard score is below `SCORE_THRESHOLD` (default 0.55), the skill calls DeepSeek (`deepseek/deepseek-v4-flash`) with a structured prompt to propose a short `name` and one-sentence `description` for a brand-new collection that would fit the orphan document.

6. **Persist audit record** — a `SkillInvocation` row is written via `persist_skill_invocation`; failures are silently swallowed so they never break the user-facing response.

## Fallback behaviour

- If the semantic search endpoint is unavailable (503 / 404), the Jaccard heuristic is used automatically — there is no hard failure.
- If the DeepSeek LLM call fails (network error, quota, etc.), the skill returns `{"name": "Uncategorized", "description": "", "reason": "..."}` as the proposal rather than raising.
