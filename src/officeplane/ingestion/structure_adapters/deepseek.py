"""Ask DeepSeek to extract a hierarchical structure from per-page text."""
from __future__ import annotations

import json
import logging
from typing import Optional

import litellm

from officeplane.ingestion.prompts import (
    STRUCTURE_EXTRACTION_PROMPT,
    SYSTEM_PROMPT,
)

log = logging.getLogger("officeplane.ingestion.structure_adapters.deepseek")


class DeepSeekStructureAdapter:
    """Pure-text structure extractor backed by deepseek/deepseek-v4-flash."""

    def __init__(
        self,
        model: str = "deepseek/deepseek-v4-flash",
        max_pages_per_call: int = 60,
        request_timeout: int = 240,
    ):
        self._model = model
        self._max_pages_per_call = max_pages_per_call
        self._timeout = request_timeout

    @property
    def model_name(self) -> str:
        return self._model

    async def analyze(self, pages: list[dict], filename: Optional[str] = None) -> dict:
        """Return a structure dict in the shape ``parse_full_response`` expects."""
        if not pages:
            return {"title": "Untitled", "chapters": []}

        # Chunk into batches if very long; merge after.
        all_results = []
        chunk_size = self._max_pages_per_call
        for offset in range(0, len(pages), chunk_size):
            chunk = pages[offset : offset + chunk_size]
            user_message = self._format_pages(chunk, filename=filename)
            log.info(
                "structuring %d pages (offset %d) via %s",
                len(chunk),
                offset,
                self._model,
            )
            response = await litellm.acompletion(
                model=self._model,
                temperature=0.0,
                request_timeout=self._timeout,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": STRUCTURE_EXTRACTION_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            raw = response.choices[0].message.content or ""
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # Try stripping ```json fences
                stripped = raw.strip()
                if stripped.startswith("```"):
                    lines = stripped.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    stripped = "\n".join(lines).strip()
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    log.warning("DeepSeek structure response not JSON; len=%d", len(raw))
                    parsed = {"title": "Document", "chapters": []}
            all_results.append(parsed)

        if len(all_results) == 1:
            return all_results[0]
        # Multiple chunks — fold them similarly to _merge_batch_results, but for
        # the text path we re-assemble at the chapter level.
        return self._merge_chunked_results(all_results)

    def _format_pages(self, pages: list[dict], *, filename: Optional[str]) -> str:
        header = f"Document: {filename}\n\n" if filename else ""
        body = "\n\n".join(
            f"--- PAGE {p['page_number']} ---\n{p.get('text', '')}".strip()
            for p in pages
        )
        return header + body

    def _merge_chunked_results(self, results: list[dict]) -> dict:
        merged_chapters: list[dict] = []
        title = None
        author = None
        document_summary = None
        topics: list[str] = []
        seen_topics: set[str] = set()
        key_entities: dict[str, list] = {}
        for r in results:
            if title is None and r.get("title"):
                title = r["title"]
            if author is None and r.get("author"):
                author = r["author"]
            if document_summary is None and r.get("document_summary"):
                document_summary = r["document_summary"]
            for tag in r.get("topics", []) or []:
                if isinstance(tag, str) and tag not in seen_topics:
                    seen_topics.add(tag)
                    topics.append(tag)
            for k, vs in (r.get("key_entities", {}) or {}).items():
                if isinstance(vs, list):
                    bucket = key_entities.setdefault(k, [])
                    for v in vs:
                        if v not in bucket:
                            bucket.append(v)
            merged_chapters.extend(r.get("chapters", []) or [])
        return {
            "title": title or "Document",
            "author": author,
            "document_summary": document_summary,
            "topics": topics,
            "key_entities": key_entities,
            "chapters": merged_chapters,
        }
