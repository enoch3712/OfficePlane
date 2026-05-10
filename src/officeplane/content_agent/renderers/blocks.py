"""Typed block data classes — the schema rendered by docx_blocks / pptx_blocks.

Mirrors the course-document/SKILL.md block-based schema:
  schema_version: "1.0"
  title: str
  modules:
    - id: str
      title: str (optional, derived from first title-block if absent)
      lessons:
        - id: str
          title: str
          order: int
          blocks: [Block, ...]

Block types: title | text | table | image
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


BlockType = Literal["title", "text", "table", "image"]


@dataclass
class SourceReference:
    document_id: Optional[str] = None
    document_title: Optional[str] = None
    chapter_id: Optional[str] = None
    chapter_title: Optional[str] = None
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    page_numbers: list[int] = field(default_factory=list)


@dataclass
class Block:
    type: BlockType
    content: Optional[str] = None  # title/text: plain string; table: JSON string {"headers","rows"}
    alt: Optional[str] = None
    object_key: Optional[str] = None
    order: int = 0
    source_references: list[SourceReference] = field(default_factory=list)


@dataclass
class Lesson:
    id: str
    title: str
    order: int = 0
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Module:
    id: str
    title: str = ""
    order: int = 0
    lessons: list[Lesson] = field(default_factory=list)


@dataclass
class BlocksDocument:
    title: str = "Untitled"
    schema_version: str = "1.0"
    modules: list[Module] = field(default_factory=list)


def parse_blocks_document(data: dict) -> BlocksDocument:
    """Lenient parse: missing fields default; unknown keys ignored."""
    doc = BlocksDocument(
        title=str(data.get("title") or "Untitled"),
        schema_version=str(data.get("schema_version") or "1.0"),
    )
    for m_idx, m in enumerate(data.get("modules") or []):
        if not isinstance(m, dict):
            continue
        module = Module(
            id=str(m.get("id") or f"module-{m_idx}"),
            title=str(m.get("title") or ""),
            order=int(m.get("order") or m_idx),
        )
        for l_idx, l in enumerate(m.get("lessons") or []):
            if not isinstance(l, dict):
                continue
            lesson = Lesson(
                id=str(l.get("id") or f"lesson-{m_idx}-{l_idx}"),
                title=str(l.get("title") or ""),
                order=int(l.get("order") or l_idx),
            )
            for b_idx, b in enumerate(l.get("blocks") or []):
                if not isinstance(b, dict):
                    continue
                btype = b.get("type")
                if btype not in ("title", "text", "table", "image"):
                    continue
                refs = []
                for r in b.get("source_references") or []:
                    if isinstance(r, dict):
                        refs.append(SourceReference(
                            document_id=r.get("document_id"),
                            document_title=r.get("document_title"),
                            chapter_id=r.get("chapter_id"),
                            chapter_title=r.get("chapter_title"),
                            section_id=r.get("section_id"),
                            section_title=r.get("section_title"),
                            page_numbers=list(r.get("page_numbers") or []),
                        ))
                lesson.blocks.append(Block(
                    type=btype,
                    content=b.get("content"),
                    alt=b.get("alt"),
                    object_key=b.get("object_key"),
                    order=int(b.get("order") or b_idx),
                    source_references=refs,
                ))
            module.lessons.append(lesson)
        doc.modules.append(module)
    return doc
