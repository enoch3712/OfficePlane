"""Save generated content to the document store."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from officeplane.documents.store import DocumentStore

log = logging.getLogger("officeplane.content_agent.storage")


async def save_to_document_store(
    job_id: str,
    workspace: Path,
    output_format: str,
    prompt: str,
) -> Optional[str]:
    """
    Save generated presentation to the document store.

    Creates a Document with chapters/sections/pages representing each slide.
    Stores the original file bytes in source_file.

    Returns the document ID, or None on failure.
    """
    store = DocumentStore()
    await store.connect()

    try:
        # Find the primary output file
        primary_file = _find_primary_output(workspace, output_format)
        if not primary_file:
            log.error("No output file found in workspace %s", workspace)
            return None

        # Read file bytes
        file_bytes = primary_file.read_bytes()
        file_name = primary_file.name

        # Load metadata if available
        metadata = _load_metadata(workspace)

        # Create the document
        title = metadata.get("title", f"Generated: {prompt[:80]}")
        doc = await store.create_document(
            title=title,
            author="Content Agent",
            metadata={
                "source": "content_agent",
                "job_id": job_id,
                "prompt": prompt,
                "output_format": output_format,
                **metadata,
            },
        )

        # Store the original file bytes
        pool = await store._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE documents
                SET source_file = $1, source_format = $2, file_name = $3
                WHERE id = $4
                """,
                file_bytes,
                output_format,
                file_name,
                doc.id,
            )

        # Create document structure from slides
        slides = metadata.get("slides", [])
        if slides:
            await _create_slide_structure(store, doc.id, slides)
        else:
            # Create a single chapter/section/page with the prompt as content
            chapter = await store.create_chapter(doc.id, "Presentation")
            section = await store.create_section(chapter.id, "Slides")
            await store.create_page(section.id, f"Generated from prompt: {prompt}")

        log.info("Saved document %s for job %s", doc.id, job_id)
        return str(doc.id)

    except Exception as e:
        log.error("Failed to save document for job %s: %s", job_id, e)
        return None
    finally:
        await store.close()


async def _create_slide_structure(
    store: DocumentStore,
    document_id: UUID,
    slides: list[Dict[str, Any]],
) -> None:
    """Create document hierarchy from slide metadata."""
    chapter = await store.create_chapter(document_id, "Slides")
    section = await store.create_section(chapter.id, "Content")

    for i, slide in enumerate(slides):
        title = slide.get("title", f"Slide {i + 1}")
        content_parts = [f"# {title}"]
        if desc := slide.get("description"):
            content_parts.append(desc)
        if notes := slide.get("notes"):
            content_parts.append(f"\n---\nNotes: {notes}")

        content = "\n\n".join(content_parts)
        await store.create_page(section.id, content, page_number=i + 1)


def _find_primary_output(workspace: Path, output_format: str) -> Optional[Path]:
    """Find the primary output file in the workspace."""
    # Look for named file first
    candidates = [
        workspace / f"presentation.{output_format}",
        workspace / f"output.{output_format}",
    ]
    for c in candidates:
        if c.exists():
            return c

    # Fall back to any file with the right extension
    for f in workspace.rglob(f"*.{output_format}"):
        return f

    return None


def _load_metadata(workspace: Path) -> Dict[str, Any]:
    """Load metadata.json from workspace if it exists."""
    meta_file = workspace / "metadata.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to load metadata.json: %s", e)
    return {}
