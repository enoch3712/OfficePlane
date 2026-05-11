"""Resolve Figure.src by either using an existing file or generating from prompt.

The Document tree's Figure block can be empty (src=None, prompt="cuff diagram").
Renderers call resolve_figure_image() right before embedding — if the prompt is
present the configured ImageProvider produces a PNG and writes it to
<workspace>/images/<fig.id>.png, then the renderer embeds that path.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from officeplane.content_agent.renderers.document import Figure
from officeplane.content_agent.image_provider import get_provider

log = logging.getLogger("officeplane.image_embed")


def resolve_figure_image(fig: Figure, workspace_dir: Path) -> Path | None:
    """Synchronous wrapper used by the docx/pptx renderers (which are sync)."""
    # If src is a real file, use it.
    if fig.src:
        candidate = Path(fig.src)
        if candidate.exists():
            return candidate

    if not fig.prompt:
        return None

    out_dir = workspace_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{fig.id}.png"

    if out_path.exists():
        return out_path

    try:
        provider = get_provider()
        # Run async provider in a fresh event loop if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in a running loop — use a new event loop in a thread
                png_bytes = asyncio.new_event_loop().run_until_complete(
                    provider.generate_image(fig.prompt)
                )
            else:
                png_bytes = loop.run_until_complete(provider.generate_image(fig.prompt))
        except RuntimeError:
            png_bytes = asyncio.run(provider.generate_image(fig.prompt))
    except Exception as e:
        log.warning("image generation failed for figure %s: %s", fig.id, e)
        return None

    out_path.write_bytes(png_bytes)
    return out_path
