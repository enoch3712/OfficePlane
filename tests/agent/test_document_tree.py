"""Tests for the agnostic Document tree dataclasses and parse_document."""

from officeplane.content_agent.renderers.document import (
    Document,
    Section,
    Heading,
    Paragraph,
    List as ListBlock,
    Table,
    Figure,
    Code,
    Callout,
    Quote,
    Divider,
    Attribution,
    parse_document,
)


def test_parse_minimal_document():
    """A bare-minimum dict with no children round-trips to a Document."""
    data = {"type": "document"}
    doc = parse_document(data)
    assert isinstance(doc, Document)
    assert doc.meta.title == "Untitled"
    assert doc.meta.language == "en"
    assert doc.children == []
    assert doc.attributions == []
    assert doc.schema_version == "1.0"


def test_recursive_sections_arbitrary_depth():
    """Sections can nest at arbitrary depth; children are parsed recursively."""
    data = {
        "type": "document",
        "meta": {"title": "Deep Doc"},
        "children": [
            {
                "type": "section",
                "id": "s1",
                "level": 1,
                "heading": "Top",
                "children": [
                    {
                        "type": "section",
                        "id": "s1-1",
                        "level": 2,
                        "heading": "Middle",
                        "children": [
                            {
                                "type": "section",
                                "id": "s1-1-1",
                                "level": 3,
                                "heading": "Deep",
                                "children": [
                                    {
                                        "type": "paragraph",
                                        "id": "p1",
                                        "text": "Deep content",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    doc = parse_document(data)
    assert doc.meta.title == "Deep Doc"
    top = doc.children[0]
    assert isinstance(top, Section)
    assert top.level == 1
    assert top.heading == "Top"
    middle = top.children[0]
    assert isinstance(middle, Section)
    assert middle.level == 2
    deep = middle.children[0]
    assert isinstance(deep, Section)
    assert deep.level == 3
    leaf = deep.children[0]
    assert isinstance(leaf, Paragraph)
    assert leaf.text == "Deep content"


def test_all_block_types_round_trip():
    """All nine leaf block types are parsed without error."""
    data = {
        "type": "document",
        "children": [
            {"type": "heading", "id": "h1", "level": 1, "text": "Hello"},
            {"type": "paragraph", "id": "p1", "text": "World"},
            {
                "type": "list",
                "id": "l1",
                "ordered": True,
                "items": [
                    {"type": "paragraph", "id": "li1", "text": "Item 1"},
                    {"type": "paragraph", "id": "li2", "text": "Item 2"},
                ],
            },
            {
                "type": "table",
                "id": "t1",
                "headers": ["Col A", "Col B"],
                "rows": [["1", "2"], ["3", "4"]],
            },
            {
                "type": "figure",
                "id": "fig1",
                "src": "img.png",
                "caption": "A figure",
                "alt": "alt text",
                "prompt": None,
            },
            {"type": "code", "id": "c1", "lang": "python", "text": "print('hi')"},
            {"type": "callout", "id": "ca1", "variant": "note", "text": "Note this"},
            {"type": "quote", "id": "q1", "text": "Quoted"},
            {"type": "divider", "id": "d1"},
        ],
    }
    doc = parse_document(data)
    children = doc.children
    assert isinstance(children[0], Heading)
    assert children[0].level == 1
    assert children[0].text == "Hello"

    assert isinstance(children[1], Paragraph)
    assert children[1].text == "World"

    assert isinstance(children[2], ListBlock)
    assert children[2].ordered is True
    assert len(children[2].items) == 2

    assert isinstance(children[3], Table)
    assert children[3].headers == ["Col A", "Col B"]
    assert children[3].rows == [["1", "2"], ["3", "4"]]

    assert isinstance(children[4], Figure)
    assert children[4].src == "img.png"
    assert children[4].caption == "A figure"

    assert isinstance(children[5], Code)
    assert children[5].lang == "python"

    assert isinstance(children[6], Callout)
    assert children[6].variant == "note"

    assert isinstance(children[7], Quote)
    assert children[7].text == "Quoted"

    assert isinstance(children[8], Divider)


def test_auto_assigns_node_ids():
    """Nodes without an explicit id get an auto-generated short UUID."""
    data = {
        "type": "document",
        "children": [
            {"type": "paragraph", "text": "No id here"},
            {
                "type": "section",
                "level": 1,
                "heading": "Sectionless id",
                "children": [],
            },
        ],
    }
    doc = parse_document(data)
    para = doc.children[0]
    section = doc.children[1]
    assert isinstance(para, Paragraph)
    assert para.id != "" and para.id is not None
    assert isinstance(section, Section)
    assert section.id != "" and section.id is not None


def test_document_to_dict_round_trip():
    from officeplane.content_agent.renderers.document import (
        parse_document,
        document_to_dict,
    )

    src = {
        "type": "document",
        "meta": {"title": "T"},
        "children": [
            {
                "type": "section",
                "id": "s1",
                "level": 1,
                "heading": "H",
                "children": [
                    {"type": "paragraph", "id": "p1", "text": "x"},
                    {
                        "type": "list",
                        "ordered": True,
                        "items": [{"type": "paragraph", "text": "i"}],
                    },
                    {"type": "table", "headers": ["a"], "rows": [["b"]]},
                ],
            },
        ],
        "attributions": [{"node_id": "p1", "document_id": "d1"}],
    }
    doc = parse_document(src)
    out = document_to_dict(doc)
    # Round-trip stable through parse_document
    doc2 = parse_document(out)
    assert document_to_dict(doc2) == out
