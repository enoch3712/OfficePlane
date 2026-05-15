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


def _run_async_safe(coro):
    """Run an async coroutine from sync code regardless of whether the caller
    is already inside a running event loop.

    The pptx/docx renderers are sync but are dispatched from within an async
    FastAPI handler, so `asyncio.get_event_loop()` finds an already-running
    loop and we cannot `run_until_complete` on it. Solution: run the coroutine
    in a fresh loop on a worker thread.
    """
    import concurrent.futures

    def _runner():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_runner).result()


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
        png_bytes = _run_async_safe(provider.generate_image(fig.prompt))
    except Exception as e:
        log.warning("image generation failed for figure %s: %s", fig.id, e)
        return None

    out_path.write_bytes(png_bytes)
    return out_path
