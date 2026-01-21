"""
Display utilities for action plan trees.

Provides multiple output formats for visualizing action plans:
- ASCII tree
- Mermaid diagrams
- Markdown
- JSON
"""

from __future__ import annotations

from typing import Any, Dict, List

from officeplane.components.planning.models import ActionNode, ActionPlan


class PlanDisplayer:
    """Utilities for displaying action plans in various formats."""

    @staticmethod
    def to_tree_text(plan: ActionPlan, max_depth: int = -1) -> str:
        """
        Generate ASCII tree visualization.

        Args:
            plan: The action plan to visualize
            max_depth: Maximum depth to display (-1 for unlimited)

        Returns:
            ASCII tree string
        """
        lines = [
            f"Plan: {plan.title}",
            f"Prompt: {plan.original_prompt}",
            "",
            f"Summary: {plan.total_nodes} actions",
            f"  - Documents: {plan.action_counts.get('create_document', 0)}",
            f"  - Chapters: {plan.action_counts.get('add_chapter', 0)}",
            f"  - Sections: {plan.action_counts.get('add_section', 0)}",
            f"  - Pages: {plan.action_counts.get('write_page', 0)}",
            "",
            "Tree:",
        ]

        def render_node(
            node: ActionNode, prefix: str = "", is_last: bool = True, depth: int = 0
        ):
            if max_depth >= 0 and depth > max_depth:
                return

            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            # Truncate description if too long
            desc = node.description[:50] + "..." if len(node.description) > 50 else node.description
            lines.append(f"{prefix}{connector}[{node.id}] {node.action_name}")
            if desc:
                child_prefix = prefix + ("    " if is_last else "\u2502   ")
                lines.append(f"{child_prefix}  \u2192 {desc}")

            child_prefix = prefix + ("    " if is_last else "\u2502   ")
            for i, child in enumerate(node.children):
                render_node(child, child_prefix, i == len(node.children) - 1, depth + 1)

        for i, root in enumerate(plan.roots):
            render_node(root, "", i == len(plan.roots) - 1)

        return "\n".join(lines)

    @staticmethod
    def _escape_mermaid(text: str) -> str:
        """Escape special characters for Mermaid labels."""
        # Replace characters that break Mermaid syntax
        text = text.replace('"', "'")
        text = text.replace("(", "[")
        text = text.replace(")", "]")
        text = text.replace("{", "[")
        text = text.replace("}", "]")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace("&", "&amp;")
        text = text.replace("#", "&#35;")
        return text

    @staticmethod
    def to_mermaid(plan: ActionPlan, include_fences: bool = True) -> str:
        """
        Generate Mermaid diagram syntax.

        Returns a flowchart that can be rendered by Mermaid.js.

        Args:
            plan: The action plan to visualize
            include_fences: Whether to include markdown code fences

        Returns:
            Mermaid diagram string
        """
        lines = []
        if include_fences:
            lines.append("```mermaid")
        lines.append("graph TD")

        def add_node(node: ActionNode, parent_id: str | None = None):
            # Format and escape label
            label = node.action_name.replace("_", " ").title()
            desc = node.description[:25] + "..." if len(node.description) > 25 else node.description
            desc = PlanDisplayer._escape_mermaid(desc)
            label = PlanDisplayer._escape_mermaid(label)
            if desc:
                label = f"{label}<br/>{desc}"

            # Use different shapes based on action type - all use quotes for safety
            if node.action_name == "create_document":
                shape = f'{node.id}(["{label}"])'  # Stadium shape
            elif node.action_name == "add_chapter":
                shape = f'{node.id}["{label}"]'  # Rectangle
            elif node.action_name == "add_section":
                shape = f'{node.id}("{label}")'  # Rounded
            elif node.action_name == "write_page":
                shape = f'{node.id}{{"{label}"}}'  # Diamond/rhombus
            else:
                shape = f'{node.id}["{label}"]'

            lines.append(f"    {shape}")

            if parent_id:
                lines.append(f"    {parent_id} --> {node.id}")

            for child in node.children:
                add_node(child, node.id)

        for root in plan.roots:
            add_node(root)

        # Add styling
        lines.append("")
        lines.append("    classDef document fill:#e1f5fe,stroke:#01579b")
        lines.append("    classDef chapter fill:#f3e5f5,stroke:#4a148c")
        lines.append("    classDef section fill:#e8f5e9,stroke:#1b5e20")
        lines.append("    classDef page fill:#fff3e0,stroke:#e65100")

        # Apply styles
        doc_nodes = [n.id for n in plan._iter_all_nodes() if n.action_name == "create_document"]
        ch_nodes = [n.id for n in plan._iter_all_nodes() if n.action_name == "add_chapter"]
        sec_nodes = [n.id for n in plan._iter_all_nodes() if n.action_name == "add_section"]
        pg_nodes = [n.id for n in plan._iter_all_nodes() if n.action_name == "write_page"]

        if doc_nodes:
            lines.append(f"    class {','.join(doc_nodes)} document")
        if ch_nodes:
            lines.append(f"    class {','.join(ch_nodes)} chapter")
        if sec_nodes:
            lines.append(f"    class {','.join(sec_nodes)} section")
        if pg_nodes:
            lines.append(f"    class {','.join(pg_nodes)} page")

        if include_fences:
            lines.append("```")
        return "\n".join(lines)

    @staticmethod
    def to_markdown(plan: ActionPlan) -> str:
        """
        Generate markdown representation.

        Args:
            plan: The action plan to visualize

        Returns:
            Markdown string
        """
        lines = [
            f"# Action Plan: {plan.title}",
            "",
            f"**Original Request:** {plan.original_prompt}",
            "",
            "## Summary",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Total Actions | {plan.total_nodes} |",
            f"| Documents | {plan.action_counts.get('create_document', 0)} |",
            f"| Chapters | {plan.action_counts.get('add_chapter', 0)} |",
            f"| Sections | {plan.action_counts.get('add_section', 0)} |",
            f"| Pages | {plan.action_counts.get('write_page', 0)} |",
            "",
            "## Structure",
            "",
        ]

        def render_node(node: ActionNode, level: int = 0):
            indent = "  " * level
            bullet = "-" if level == 0 else "-"

            # Format based on action type
            if node.action_name == "create_document":
                lines.append(f"{indent}{bullet} **Document:** {node.description or node.inputs.get('title', 'Untitled')}")
            elif node.action_name == "add_chapter":
                lines.append(f"{indent}{bullet} **Chapter:** {node.description or node.inputs.get('title', 'Untitled')}")
            elif node.action_name == "add_section":
                lines.append(f"{indent}{bullet} *Section:* {node.description or node.inputs.get('title', 'Untitled')}")
            elif node.action_name == "write_page":
                lines.append(f"{indent}{bullet} Page: {node.description or 'Page ' + str(node.inputs.get('page_number', '?'))}")
            else:
                lines.append(f"{indent}{bullet} {node.action_name}: {node.description}")

            for child in node.children:
                render_node(child, level + 1)

        for root in plan.roots:
            render_node(root)

        return "\n".join(lines)

    @staticmethod
    def to_json(plan: ActionPlan, include_inputs: bool = True) -> Dict[str, Any]:
        """
        Convert plan to JSON-serializable dict.

        Args:
            plan: The action plan to convert
            include_inputs: Whether to include action inputs

        Returns:
            JSON-serializable dictionary
        """

        def node_to_dict(node: ActionNode) -> Dict[str, Any]:
            result: Dict[str, Any] = {
                "id": node.id,
                "action": node.action_name,
                "description": node.description,
                "status": node.status,
            }
            if include_inputs:
                result["inputs"] = node.inputs
            if node.children:
                result["children"] = [node_to_dict(c) for c in node.children]
            return result

        return {
            "id": plan.id,
            "title": plan.title,
            "original_prompt": plan.original_prompt,
            "created_at": plan.created_at.isoformat(),
            "summary": plan.to_summary(),
            "tree": [node_to_dict(root) for root in plan.roots],
        }

    @staticmethod
    def to_compact_tree(plan: ActionPlan) -> str:
        """
        Generate a compact single-line-per-node tree.

        Useful for logging or quick inspection.

        Args:
            plan: The action plan to visualize

        Returns:
            Compact tree string
        """
        lines = [f"[{plan.id}] {plan.title} ({plan.total_nodes} actions)"]

        def render_node(node: ActionNode, prefix: str = ""):
            symbol = {
                "create_document": "D",
                "add_chapter": "C",
                "add_section": "S",
                "write_page": "P",
            }.get(node.action_name, "?")

            title = (
                node.inputs.get("title")
                or node.description[:20]
                or node.action_name
            )
            lines.append(f"{prefix}[{symbol}] {title}")

            for i, child in enumerate(node.children):
                child_prefix = prefix + ("  " if i == len(node.children) - 1 else "| ")
                render_node(child, child_prefix)

        for root in plan.roots:
            render_node(root, "  ")

        return "\n".join(lines)
