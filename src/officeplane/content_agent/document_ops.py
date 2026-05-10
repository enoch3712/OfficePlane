"""Tree-mutation operations for the agnostic Document tree.

All operations identify nodes by their string ``id``.  The ``walk_nodes``
generator is the single workhorse; every other function is built on top of it.
"""

from __future__ import annotations

from typing import Any, Iterator

from officeplane.content_agent.renderers.document import (
    Document,
    Section,
    Heading,
    Paragraph,
    List,
    Table,
    Figure,
    Code,
    Callout,
    Quote,
    Divider,
)

# Union of every node type that can appear in a Document tree.
Node = Section | Heading | Paragraph | List | Table | Figure | Code | Callout | Quote | Divider

# Nodes that can own a .children list (i.e. are containers).
Container = Document | Section


# ---------------------------------------------------------------------------
# walk_nodes — DFS generator
# ---------------------------------------------------------------------------


def walk_nodes(doc: Document) -> Iterator[tuple[Node, list[str]]]:
    """DFS yielding ``(node, path_of_ids_from_root_to_node_inclusive)``.

    The Document root itself is *not* yielded — only nodes reachable through
    ``doc.children`` (and their descendants).
    """

    def _recurse(children: list[Any], prefix: list[str]) -> Iterator[tuple[Node, list[str]]]:
        for node in children:
            path = prefix + [node.id]
            yield node, path
            if isinstance(node, Section):
                yield from _recurse(node.children, path)

    yield from _recurse(doc.children, [])


# ---------------------------------------------------------------------------
# find_node
# ---------------------------------------------------------------------------


def find_node(doc: Document, node_id: str) -> tuple[Node | None, Container | None]:
    """Return ``(node, parent_container)`` for the node with ``node_id``.

    *parent_container* is the ``Section`` or ``Document`` whose ``.children``
    list contains the node.  Returns ``(None, None)`` if not found.
    """

    def _search(children: list[Any], parent: Container) -> tuple[Node | None, Container | None]:
        for node in children:
            if node.id == node_id:
                return node, parent
            if isinstance(node, Section):
                result, found_parent = _search(node.children, node)
                if result is not None:
                    return result, found_parent
        return None, None

    return _search(doc.children, doc)


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------


def insert_after(doc: Document, anchor_id: str, node: Node) -> None:
    """Insert ``node`` as the next sibling of the node identified by ``anchor_id``.

    Raises ``KeyError`` if no node with ``anchor_id`` exists.
    """
    anchor, parent = find_node(doc, anchor_id)
    if anchor is None or parent is None:
        raise KeyError(anchor_id)
    idx = parent.children.index(anchor)
    parent.children.insert(idx + 1, node)


def insert_before(doc: Document, anchor_id: str, node: Node) -> None:
    """Insert ``node`` as the previous sibling of the node identified by ``anchor_id``.

    Raises ``KeyError`` if no node with ``anchor_id`` exists.
    """
    anchor, parent = find_node(doc, anchor_id)
    if anchor is None or parent is None:
        raise KeyError(anchor_id)
    idx = parent.children.index(anchor)
    parent.children.insert(idx, node)


def insert_as_child(
    doc: Document,
    parent_id: str,
    node: Node,
    position: int | None = None,
) -> None:
    """Append (or insert at ``position``) ``node`` into the children of ``parent_id``.

    ``parent_id`` must identify a ``Section`` node.

    Raises:
        KeyError: if no node with ``parent_id`` exists.
        ValueError: if the identified node is not a ``Section``.
    """
    parent_node, _ = find_node(doc, parent_id)
    if parent_node is None:
        raise KeyError(parent_id)
    if not isinstance(parent_node, Section):
        raise ValueError(
            f"insert_as_child: node '{parent_id}' is {type(parent_node).__name__}, not a Section"
        )
    if position is None:
        parent_node.children.append(node)
    else:
        parent_node.children.insert(position, node)


def replace_node(doc: Document, target_id: str, node: Node) -> None:
    """Swap the node identified by ``target_id`` with ``node`` in-place.

    Sibling order is preserved; the exact index is reused.

    Raises ``KeyError`` if no node with ``target_id`` exists.
    """
    target, parent = find_node(doc, target_id)
    if target is None or parent is None:
        raise KeyError(target_id)
    idx = parent.children.index(target)
    parent.children[idx] = node


def delete_node(doc: Document, target_id: str) -> None:
    """Remove the node identified by ``target_id`` from its parent's children.

    Raises ``KeyError`` if no node with ``target_id`` exists.
    """
    target, parent = find_node(doc, target_id)
    if target is None or parent is None:
        raise KeyError(target_id)
    parent.children.remove(target)
