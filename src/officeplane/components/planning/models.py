"""
Data models for action plan trees.

Provides structures for representing planned actions as a tree,
with placeholder IDs for dependencies between parent and child nodes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class PlaceholderID(BaseModel):
    """
    Represents a placeholder ID that will be resolved at execution time.

    Format: $node_id.output_field (e.g., "$node_1.id" or "$node_doc.document_id")

    Used to reference outputs from parent nodes that aren't yet available
    during plan generation.
    """

    node_id: str = Field(..., description="Reference to the node that produces this ID")
    output_field: str = Field(
        "id", description="Field name in the output model to extract"
    )

    def __str__(self) -> str:
        return f"${self.node_id}.{self.output_field}"

    def __repr__(self) -> str:
        return f"PlaceholderID({self.node_id}.{self.output_field})"

    @classmethod
    def parse(cls, ref: str) -> "PlaceholderID":
        """
        Parse a placeholder reference string like '$node_1.id'.

        Args:
            ref: Placeholder string starting with $

        Returns:
            PlaceholderID instance

        Raises:
            ValueError: If ref doesn't start with $
        """
        if not ref.startswith("$"):
            raise ValueError(f"Placeholder must start with $: {ref}")
        parts = ref[1:].split(".", 1)
        return cls(
            node_id=parts[0],
            output_field=parts[1] if len(parts) > 1 else "id",
        )

    @classmethod
    def is_placeholder(cls, value: Any) -> bool:
        """Check if a value is a placeholder reference string."""
        return isinstance(value, str) and value.startswith("$")


class NodeStatus(str, Enum):
    """Status of a plan node during execution."""

    PENDING = "pending"  # Not yet started
    READY = "ready"  # All dependencies resolved, ready to execute
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Execution failed
    SKIPPED = "skipped"  # Skipped (e.g., due to parent failure)


class ActionNode(BaseModel):
    """
    A single action in the plan tree.

    Represents one call to a component action with its inputs,
    including placeholders for values that depend on parent nodes.

    Tree structure is maintained via parent_id and children fields.
    """

    id: str = Field(default_factory=lambda: f"node_{uuid4().hex[:8]}")
    action_name: str = Field(
        ..., description="Name of the action (e.g., 'create_document', 'add_chapter')"
    )
    description: str = Field("", description="Human-readable description of this step")

    # Input parameters - can contain PlaceholderID references as strings
    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters, may contain $placeholder references",
    )

    # Tree structure
    parent_id: Optional[str] = Field(None, description="Parent node ID in the tree")
    children: List["ActionNode"] = Field(
        default_factory=list, description="Child nodes"
    )

    # Execution state (for later execution phase)
    status: NodeStatus = Field(default=NodeStatus.PENDING)
    output: Optional[Dict[str, Any]] = Field(
        None, description="Action output after execution"
    )
    error: Optional[str] = Field(None, description="Error message if failed")

    # Metadata
    order_index: int = Field(0, description="Execution order among siblings")
    estimated_tokens: Optional[int] = Field(
        None, description="Estimated LLM tokens for content generation"
    )

    model_config = ConfigDict(use_enum_values=True)

    def get_placeholder_dependencies(self) -> List[PlaceholderID]:
        """Extract all placeholder dependencies from inputs."""
        placeholders = []
        for value in self.inputs.values():
            if PlaceholderID.is_placeholder(value):
                placeholders.append(PlaceholderID.parse(value))
        return placeholders

    def get_dependency_node_ids(self) -> List[str]:
        """Get IDs of nodes this node depends on."""
        return list(set(p.node_id for p in self.get_placeholder_dependencies()))

    def to_display_dict(self, include_children: bool = True) -> Dict[str, Any]:
        """Convert to a display-friendly dictionary format."""
        result: Dict[str, Any] = {
            "id": self.id,
            "action": self.action_name,
            "description": self.description,
            "inputs": self.inputs,
            "status": self.status,
        }
        if include_children:
            result["children"] = [c.to_display_dict() for c in self.children]
        return result

    def count_descendants(self) -> int:
        """Count total number of descendant nodes."""
        count = len(self.children)
        for child in self.children:
            count += child.count_descendants()
        return count


class ActionPlan(BaseModel):
    """
    A complete action plan tree for document authoring.

    The plan is a forest (list of trees), typically with one root
    for create_document and all chapters/sections/pages as descendants.
    """

    id: str = Field(default_factory=lambda: f"plan_{uuid4().hex[:8]}")
    title: str = Field(..., description="Plan title (derived from user prompt)")
    original_prompt: str = Field(..., description="The user's original request")

    # The plan tree(s)
    roots: List[ActionNode] = Field(
        default_factory=list, description="Root nodes of the plan"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    total_nodes: int = Field(0, description="Total number of action nodes")
    estimated_pages: int = Field(0, description="Estimated page count")

    # Summary statistics
    action_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count of each action type in the plan"
    )

    model_config = ConfigDict(validate_assignment=True)

    def model_post_init(self, __context: Any) -> None:
        """Compute statistics after initialization."""
        self._compute_stats()

    def _compute_stats(self) -> None:
        """Compute plan statistics from the tree."""
        # Count all nodes
        all_nodes = list(self._iter_all_nodes())
        self.total_nodes = len(all_nodes)

        # Count by action type
        self.action_counts = {}
        for node in all_nodes:
            self.action_counts[node.action_name] = (
                self.action_counts.get(node.action_name, 0) + 1
            )

        # Estimate pages
        self.estimated_pages = self.action_counts.get("write_page", 0)

    def _iter_all_nodes(self):
        """Iterate over all nodes in the plan (depth-first)."""

        def visit(node: ActionNode):
            yield node
            for child in node.children:
                yield from visit(child)

        for root in self.roots:
            yield from visit(root)

    def get_node(self, node_id: str) -> Optional[ActionNode]:
        """Get a node by ID."""
        for node in self._iter_all_nodes():
            if node.id == node_id:
                return node
        return None

    def get_execution_order(self) -> List[ActionNode]:
        """
        Return nodes in execution order (topological sort).

        Parents before children, siblings by order_index.
        """
        result: List[ActionNode] = []

        def visit(node: ActionNode):
            result.append(node)
            for child in sorted(node.children, key=lambda n: n.order_index):
                visit(child)

        for root in self.roots:
            visit(root)
        return result

    def to_tree_string(self) -> str:
        """Generate a text tree visualization."""
        lines = [
            f"Plan: {self.title}",
            f"Prompt: {self.original_prompt}",
            "",
            f"Summary: {self.total_nodes} actions, {self.action_counts.get('add_chapter', 0)} chapters, "
            f"{self.action_counts.get('add_section', 0)} sections, {self.estimated_pages} pages",
            "",
        ]

        def render_node(node: ActionNode, prefix: str = "", is_last: bool = True):
            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            lines.append(
                f"{prefix}{connector}[{node.id}] {node.action_name}: {node.description}"
            )

            # Show key inputs (exclude large content)
            display_inputs = {
                k: (v[:30] + "..." if isinstance(v, str) and len(v) > 30 else v)
                for k, v in node.inputs.items()
                if k != "content"
            }
            if display_inputs:
                child_prefix = prefix + ("    " if is_last else "\u2502   ")
                input_str = ", ".join(f"{k}={v}" for k, v in display_inputs.items())
                lines.append(f"{child_prefix}    inputs: {input_str}")

            child_prefix = prefix + ("    " if is_last else "\u2502   ")
            for i, child in enumerate(node.children):
                render_node(child, child_prefix, i == len(node.children) - 1)

        for i, root in enumerate(self.roots):
            render_node(root, "", i == len(self.roots) - 1)

        return "\n".join(lines)

    def to_summary(self) -> Dict[str, Any]:
        """Generate a summary of the plan."""
        return {
            "id": self.id,
            "title": self.title,
            "total_actions": self.total_nodes,
            "action_breakdown": self.action_counts,
            "estimated_pages": self.estimated_pages,
            "structure": {
                "documents": self.action_counts.get("create_document", 0),
                "chapters": self.action_counts.get("add_chapter", 0),
                "sections": self.action_counts.get("add_section", 0),
                "pages": self.action_counts.get("write_page", 0),
            },
        }


class GeneratePlanInput(BaseModel):
    """Input for plan generation."""

    prompt: str = Field(
        ..., description="High-level user request for document creation"
    )
    max_chapters: int = Field(20, description="Maximum chapters to plan")
    max_sections_per_chapter: int = Field(
        10, description="Maximum sections per chapter"
    )
    max_pages_per_section: int = Field(5, description="Maximum pages per section")
    include_content_outlines: bool = Field(
        True, description="Whether to include content outlines for each page"
    )


class GeneratePlanOutput(BaseModel):
    """Output from plan generation."""

    plan: ActionPlan
    success: bool = True
    error: Optional[str] = None
    generation_time_ms: int = 0


class PlanSummary(BaseModel):
    """Summary view of a generated plan for API responses."""

    plan_id: str
    title: str
    original_prompt: str
    total_actions: int
    chapters: int
    sections: int
    pages: int
    tree_visualization: str
    action_breakdown: Dict[str, int]

    @classmethod
    def from_plan(cls, plan: ActionPlan) -> "PlanSummary":
        """Create a summary from an ActionPlan."""
        return cls(
            plan_id=plan.id,
            title=plan.title,
            original_prompt=plan.original_prompt,
            total_actions=plan.total_nodes,
            chapters=plan.action_counts.get("add_chapter", 0),
            sections=plan.action_counts.get("add_section", 0),
            pages=plan.action_counts.get("write_page", 0),
            tree_visualization=plan.to_tree_string(),
            action_breakdown=plan.action_counts,
        )
