---
name: citation-validator
description: Validate that each attribution in a generated document is actually supported by the cited source span; flag unsupported claims
model: gemini/gemini-embedding-001
tier: flash
inputs:
  - name: workspace_id
    type: str
    required: true
    description: Workspace directory under /data/workspaces/<id>/ containing document.json
  - name: similarity_threshold
    type: float
    required: false
    description: "Cosine similarity below this is flagged unsupported (default 0.55)"
outputs:
  - name: workspace_id
    type: str
  - name: overall_confidence
    type: float
    description: Mean similarity across all validated attributions (0..1)
  - name: validated_count
    type: int
  - name: unsupported_count
    type: int
  - name: per_node
    type: list[dict]
    description: "[{node_id, source_document_id, source_section_id, similarity, supported, source_excerpt, generated_excerpt}]"
---

# citation-validator skill

This skill cross-checks every `attribution` entry in a generated `document.json` against the actual source content stored in the database. It uses Phase 14's Gemini 768-dim embeddings to compute cosine similarity and flags any attribution whose similarity falls below the configured threshold.

## Scoring methodology

1. **Load document.json** from `CONTENT_AGENT_WORKSPACE/<workspace_id>/document.json`.
2. **Build a node-text map** by walking the document tree and extracting the textual content of every node (paragraph, heading, list, table, figure, etc.).
3. **Fetch source excerpts** for each attribution by querying the database in order of specificity: `Section` (title + summary + up to 3 pages of content) → `Chapter` (title + summary) → `Document` (title + summary). The first non-empty level wins.
4. **Embed both sides** using `EmbeddingProvider.embed_batch([generated_text, source_excerpt])` via `get_embedding_provider()`. Both texts are embedded in a single batched call to minimise API round-trips.
5. **Compute cosine similarity** with a pure-Python implementation (no extra dependencies). Orthogonal vectors yield 0.0; identical-direction vectors yield 1.0.
6. **Apply threshold** — `supported = similarity >= threshold` (default `0.55`). Nodes whose generated text has no match in the source text will produce near-zero cosine similarity and be flagged as unsupported.
7. **Aggregate** — `overall_confidence` is the arithmetic mean of per-node similarity scores.
8. **Persist** — a `SkillInvocation` audit row is written via `persist_skill_invocation`; failures are silently swallowed.

## Threshold default

`0.55` is chosen as a conservative baseline: real citations to their source material tend to score above 0.65–0.80, while hallucinated content typically scores below 0.40. Teams working with highly technical or domain-specific corpora may want to raise the threshold to 0.65.

## Edge cases

- If `attributions` is empty or absent the skill returns immediately with `validated_count=0` and a `note` field.
- If either the generated text or the source excerpt is empty (e.g., a node with no text or a dangling section reference), `similarity=0.0` and `supported=False` are reported for that node without raising.
- If the embedding provider is unavailable (missing `GOOGLE_API_KEY`, quota exceeded, etc.) the skill raises `RuntimeError` — a partial result with silent errors would be misleading.
