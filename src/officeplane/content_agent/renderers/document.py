"""Agnostic Document tree dataclasses for OfficePlane content rendering.

Block taxonomy is intentionally aligned with the CommonMark specification
(https://spec.commonmark.org/) and the Pandoc AST
(https://hackage.haskell.org/package/pandoc-types/docs/Text-Pandoc-Definition.html),
which are open, public standards maintained by their respective communities.
This vocabulary (Document / Section / Heading / Paragraph / List / Table /
Figure / Code / Callout / Quote / Divider) is therefore generic and not
proprietary to any particular organisation.

Sections nest recursively at arbitrary depth, unlike fixed-depth
course/LMS schemas (e.g. module → lesson → block). A Section may contain
other Sections or leaf Block nodes at any level. This mirrors ProseMirror's
node-tree model and makes the schema suitable for documents of any kind —
books, reports, slide decks, knowledge-base articles, etc.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Meta / Attribution
# ---------------------------------------------------------------------------


@dataclass
class DocumentMeta:
    title: str = "Untitled"
    language: str = "en"
    render_hints: dict[str, Any] = field(default_factory=dict)


@dataclass
class Attribution:
    node_id: str
    document_id: str | None = None
    document_title: str | None = None
    chapter_id: str | None = None
    section_id: str | None = None
    page_numbers: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Leaf block types
# ---------------------------------------------------------------------------


@dataclass
class Heading:
    id: str
    level: int
    text: str


@dataclass
class Paragraph:
    id: str
    text: str


@dataclass
class List:
    id: str
    ordered: bool
    items: list[Paragraph]


@dataclass
class Table:
    id: str
    headers: list[str]
    rows: list[list[str]]


@dataclass
class Figure:
    id: str
    src: str | None = None
    caption: str | None = None
    alt: str | None = None
    prompt: str | None = None


@dataclass
class Code:
    id: str
    lang: str | None
    text: str


@dataclass
class Callout:
    id: str
    variant: str  # one of: "note", "warning", "tip", "info"
    text: str


@dataclass
class Quote:
    id: str
    text: str


@dataclass
class Divider:
    id: str


# Union of all leaf block types
Block = Union[Heading, Paragraph, List, Table, Figure, Code, Callout, Quote, Divider]


# ---------------------------------------------------------------------------
# Section and Document (structural nodes)
# ---------------------------------------------------------------------------


@dataclass
class Section:
    id: str
    level: int  # 1..N
    heading: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    children: list[Section | Block] = field(default_factory=list)


@dataclass
class Document:
    meta: DocumentMeta = field(default_factory=DocumentMeta)
    children: list[Section | Block] = field(default_factory=list)
    attributions: list[Attribution] = field(default_factory=list)
    schema_version: str = "1.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    """Return a short 8-character UUID4 prefix."""
    return uuid.uuid4().hex[:8]


def _parse_meta(data: dict) -> DocumentMeta:
    meta_data = data.get("meta", {}) or {}
    return DocumentMeta(
        title=meta_data.get("title", "Untitled"),
        language=meta_data.get("language", "en"),
        render_hints=meta_data.get("render_hints", {}),
    )


def _parse_attribution(d: dict) -> Attribution:
    return Attribution(
        node_id=d.get("node_id", _new_id()),
        document_id=d.get("document_id"),
        document_title=d.get("document_title"),
        chapter_id=d.get("chapter_id"),
        section_id=d.get("section_id"),
        page_numbers=d.get("page_numbers", []),
    )


def _parse_node(d: dict) -> Section | Block | None:
    """Parse a single node dict into a Section or leaf Block. Returns None for
    unknown types (after logging a warning)."""
    t = d.get("type", "")
    node_id = d.get("id") or _new_id()

    if t == "section":
        raw_children = d.get("children", []) or []
        children: list[Section | Block] = []
        for child in raw_children:
            parsed = _parse_node(child)
            if parsed is not None:
                children.append(parsed)
        return Section(
            id=node_id,
            level=d.get("level", 1),
            heading=d.get("heading", ""),
            meta=d.get("meta", {}),
            children=children,
        )

    if t == "heading":
        return Heading(id=node_id, level=d.get("level", 1), text=d.get("text", ""))

    if t == "paragraph":
        return Paragraph(id=node_id, text=d.get("text", ""))

    if t == "list":
        raw_items = d.get("items", []) or []
        items: list[Paragraph] = []
        for item in raw_items:
            item_id = item.get("id") or _new_id()
            items.append(Paragraph(id=item_id, text=item.get("text", "")))
        return List(id=node_id, ordered=bool(d.get("ordered", False)), items=items)

    if t == "table":
        return Table(
            id=node_id,
            headers=d.get("headers", []),
            rows=d.get("rows", []),
        )

    if t == "figure":
        return Figure(
            id=node_id,
            src=d.get("src"),
            caption=d.get("caption"),
            alt=d.get("alt"),
            prompt=d.get("prompt"),
        )

    if t == "code":
        return Code(id=node_id, lang=d.get("lang"), text=d.get("text", ""))

    if t == "callout":
        return Callout(id=node_id, variant=d.get("variant", "note"), text=d.get("text", ""))

    if t == "quote":
        return Quote(id=node_id, text=d.get("text", ""))

    if t == "divider":
        return Divider(id=node_id)

    logger.warning("unknown block type %s", t)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def document_to_dict(doc: Document) -> dict[str, Any]:
    """Serialise a Document tree to a JSON-compatible dict.

    Round-trip stable with parse_document.
    """
    return {
        "type": "document",
        "schema_version": doc.schema_version,
        "meta": {
            "title": doc.meta.title,
            "language": doc.meta.language,
            "render_hints": dict(doc.meta.render_hints),
        },
        "children": [_node_to_dict(c) for c in doc.children],
        "attributions": [
            {
                "node_id": a.node_id,
                "document_id": a.document_id,
                "document_title": a.document_title,
                "chapter_id": a.chapter_id,
                "section_id": a.section_id,
                "page_numbers": list(a.page_numbers),
            }
            for a in doc.attributions
        ],
    }


def _node_to_dict(node: Any) -> dict[str, Any]:
    """Serialise a single Section or Block node to a JSON-compatible dict."""
    if isinstance(node, Section):
        return {
            "type": "section",
            "id": node.id,
            "level": node.level,
            "heading": node.heading,
            "meta": dict(node.meta),
            "children": [_node_to_dict(c) for c in node.children],
        }
    if isinstance(node, Heading):
        return {"type": "heading", "id": node.id, "level": node.level, "text": node.text}
    if isinstance(node, Paragraph):
        return {"type": "paragraph", "id": node.id, "text": node.text}
    if isinstance(node, List):
        return {
            "type": "list",
            "id": node.id,
            "ordered": node.ordered,
            "items": [_node_to_dict(i) for i in node.items],
        }
    if isinstance(node, Table):
        return {
            "type": "table",
            "id": node.id,
            "headers": list(node.headers),
            "rows": [list(r) for r in node.rows],
        }
    if isinstance(node, Figure):
        return {
            "type": "figure",
            "id": node.id,
            "src": node.src,
            "caption": node.caption,
            "alt": node.alt,
            "prompt": node.prompt,
        }
    if isinstance(node, Code):
        return {"type": "code", "id": node.id, "lang": node.lang, "text": node.text}
    if isinstance(node, Callout):
        return {"type": "callout", "id": node.id, "variant": node.variant, "text": node.text}
    if isinstance(node, Quote):
        return {"type": "quote", "id": node.id, "text": node.text}
    if isinstance(node, Divider):
        return {"type": "divider", "id": node.id}
    raise TypeError(f"unknown node type: {type(node).__name__}")


def parse_document(data: dict) -> Document:
    """Parse a dict into a :class:`Document`, lenient about missing fields.

    - Missing fields default to their dataclass defaults.
    - Unknown block types are skipped silently (a warning is logged).
    - Nodes without an explicit ``id`` key receive an auto-generated 8-char
      UUID4 prefix.
    """
    doc_type = data.get("type")
    if doc_type != "document":
        logger.warning(
            "parse_document: expected type 'document', got %r", doc_type
        )

    meta = _parse_meta(data)

    raw_children = data.get("children", []) or []
    children: list[Section | Block] = []
    for child in raw_children:
        parsed = _parse_node(child)
        if parsed is not None:
            children.append(parsed)

    raw_attributions = data.get("attributions", []) or []
    attributions = [_parse_attribution(a) for a in raw_attributions]

    return Document(
        meta=meta,
        children=children,
        attributions=attributions,
        schema_version=data.get("schema_version", "1.0"),
    )
