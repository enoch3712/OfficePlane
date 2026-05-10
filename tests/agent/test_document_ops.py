"""Tests for document tree operations (find / insert / replace / delete / walk)."""

from officeplane.content_agent.renderers.document import (
    Document,
    Section,
    Paragraph,
    parse_document,
)
from officeplane.content_agent.document_ops import (
    find_node,
    insert_after,
    insert_before,
    insert_as_child,
    replace_node,
    delete_node,
    walk_nodes,
)


def _doc():
    return parse_document({"type": "document", "children": [
        {"type": "section", "id": "s1", "level": 1, "heading": "A", "children": [
            {"type": "paragraph", "id": "p1", "text": "one"},
            {"type": "paragraph", "id": "p2", "text": "two"},
        ]},
        {"type": "section", "id": "s2", "level": 1, "heading": "B", "children": []},
    ]})


def test_find_node_by_id():
    doc = _doc()
    node, parent = find_node(doc, "p2")
    assert isinstance(node, Paragraph) and node.text == "two"
    assert isinstance(parent, Section) and parent.id == "s1"


def test_insert_after_in_middle():
    doc = _doc()
    new = Paragraph(id="p1.5", text="between")
    insert_after(doc, anchor_id="p1", node=new)
    s1 = doc.children[0]
    assert [c.id for c in s1.children] == ["p1", "p1.5", "p2"]


def test_insert_before():
    doc = _doc()
    new = Paragraph(id="p0", text="zero")
    insert_before(doc, anchor_id="p1", node=new)
    s1 = doc.children[0]
    assert [c.id for c in s1.children] == ["p0", "p1", "p2"]


def test_insert_as_child_appends():
    doc = _doc()
    new = Paragraph(id="b1", text="B body")
    insert_as_child(doc, parent_id="s2", node=new)
    s2 = doc.children[1]
    assert [c.id for c in s2.children] == ["b1"]


def test_replace_node_in_place():
    doc = _doc()
    new = Paragraph(id="p1", text="REPLACED")
    replace_node(doc, target_id="p1", node=new)
    assert doc.children[0].children[0].text == "REPLACED"


def test_delete_node():
    doc = _doc()
    delete_node(doc, target_id="p1")
    assert [c.id for c in doc.children[0].children] == ["p2"]


def test_walk_yields_every_node_with_path():
    doc = _doc()
    paths = {node.id: path for node, path in walk_nodes(doc)}
    assert paths["p1"] == ["s1", "p1"]
    assert paths["s2"] == ["s2"]
