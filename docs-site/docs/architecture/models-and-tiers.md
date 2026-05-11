---
sidebar_position: 8
title: "Models: DeepSeek-First with LiteLLM"
---

# Models: DeepSeek-First with LiteLLM

OfficePlane routes all LLM calls through [LiteLLM](https://github.com/BerriAI/litellm), a thin proxy library that exposes a unified interface across providers. Model names are passed as a single string in `provider/model-name` format, making it straightforward to swap providers without touching call sites.

## Why LiteLLM

Before LiteLLM, switching from one provider to another required updating SDK imports, authentication patterns, and response parsing in every file that called an LLM. LiteLLM collapses this to a single string:

```python
from litellm import acompletion

response = await acompletion(
    model="deepseek/deepseek-chat-v4-flash",   # or "openai/gpt-4o", "anthropic/claude-3-5-sonnet", ...
    messages=[{"role": "user", "content": prompt}],
)
```

Changing the model is an environment variable change, not a code change.

## Two Tiers: Flash and Pro

Skills declare which tier they need in `SKILL.md`. The runtime resolves the tier to a concrete model string using `model_for_tier()`.

| Tier | Default Model | Use Cases |
|------|--------------|-----------|
| `flash` | `deepseek/deepseek-chat-v4-flash` | Ingestion, bulk generation, summarization, translation, most editing tasks |
| `pro` | `deepseek/deepseek-chat-v4-pro` | Multi-step reasoning, compliance analysis, fact-checking, complex restructuring |

The `flash` tier is the default for new skills. Upgrade to `pro` only when the task requires sustained multi-step reasoning, because `pro` is ~8x slower and significantly more expensive per token.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OFFICEPLANE_AGENT_MODEL_FLASH` | `deepseek/deepseek-chat-v4-flash` | Model used for `flash`-tier skills |
| `OFFICEPLANE_AGENT_MODEL_PRO` | `deepseek/deepseek-chat-v4-pro` | Model used for `pro`-tier skills |
| `OFFICEPLANE_INGESTION_MODEL` | `deepseek/deepseek-chat-v4-flash` | Model used for the vision ingestion pipeline |

To override for a deployment, set these in `.env` or pass them to Docker:

```bash
OFFICEPLANE_AGENT_MODEL_FLASH=openai/gpt-4o-mini
OFFICEPLANE_AGENT_MODEL_PRO=openai/gpt-4o
OFFICEPLANE_INGESTION_MODEL=google/gemini-2.0-flash
```

Any model string supported by LiteLLM is valid. Run `litellm --list-models` to see all available options.

## `model_for_tier()` Factory

```python
# src/officeplane/agent/model_config.py

import os

_FLASH = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-chat-v4-flash")
_PRO   = os.getenv("OFFICEPLANE_AGENT_MODEL_PRO",   "deepseek/deepseek-chat-v4-pro")

def model_for_tier(tier: str) -> str:
    """Return the LiteLLM model string for the given tier.

    Args:
        tier: "flash" or "pro"

    Returns:
        LiteLLM provider/model-name string.
    """
    if tier == "pro":
        return _PRO
    return _FLASH
```

Skills call this at dispatch time:

```python
model = model_for_tier(skill.tier)  # "flash" or "pro" from SKILL.md frontmatter
response = await acompletion(model=model, messages=messages)
```

## Embeddings

Document chunks are embedded and stored in PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension (1536 dimensions, inner-product similarity).

| Property | Current | Pending |
|----------|---------|---------|
| **Encoder** | OpenAI `text-embedding-ada-002` | Google `embedding-001` |
| **Dimensions** | 1536 | 768 |
| **Cost** | $0.0001 / 1K tokens | Free (Gemini quota) |

The pending migration to `embedding-001` will reduce storage by ~50% and eliminate embedding costs. Existing 1536-dim vectors will be re-embedded during a one-time migration job; a compatibility flag in the `chunks` table (`embedding_model`) tracks which encoder produced each row.

Semantic search uses pgvector's `<=>` cosine distance operator:

```sql
SELECT id, content, embedding <=> $1 AS distance
FROM chunks
ORDER BY distance
LIMIT 10;
```
