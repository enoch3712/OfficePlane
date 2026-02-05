"""
Plan executor for running ActionPlan trees.

Executes action nodes in dependency order, resolving placeholders
and calling the appropriate DocumentStore methods.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from officeplane.components.planning.models import (
    ActionNode,
    ActionPlan,
    NodeStatus,
    PlaceholderID,
)
from officeplane.documents.store import DocumentStore

log = logging.getLogger("officeplane.planning.executor")


class ExecutionError(Exception):
    """Error during plan execution."""

    def __init__(self, node_id: str, action: str, message: str):
        self.node_id = node_id
        self.action = action
        super().__init__(f"[{node_id}] {action}: {message}")


class PlanExecutor:
    """
    Executes ActionPlan trees against a DocumentStore.

    Handles:
    - Topological execution order (parents before children)
    - Placeholder resolution ($node_id.field -> actual values)
    - Status updates (pending -> running -> completed/failed)
    - Callbacks for progress tracking
    """

    def __init__(
        self,
        doc_store: DocumentStore,
        on_node_start: Optional[Callable[[ActionNode], None]] = None,
        on_node_complete: Optional[Callable[[ActionNode, Dict[str, Any]], None]] = None,
        on_node_failed: Optional[Callable[[ActionNode, str], None]] = None,
    ):
        """
        Initialize the executor.

        Args:
            doc_store: DocumentStore instance (must be connected)
            on_node_start: Callback when a node starts executing
            on_node_complete: Callback when a node completes with output
            on_node_failed: Callback when a node fails with error
        """
        self.doc_store = doc_store
        self.on_node_start = on_node_start
        self.on_node_complete = on_node_complete
        self.on_node_failed = on_node_failed

        # Stores outputs from executed nodes for placeholder resolution
        self._node_outputs: Dict[str, Dict[str, Any]] = {}

    async def execute(self, plan: ActionPlan) -> Dict[str, Any]:
        """
        Execute an entire plan.

        Args:
            plan: The ActionPlan to execute

        Returns:
            Dict with execution results:
                - success: bool
                - completed: int (count of completed nodes)
                - failed: int (count of failed nodes)
                - outputs: Dict[node_id, output]
                - errors: Dict[node_id, error_message]
        """
        self._node_outputs.clear()

        completed = 0
        failed = 0
        errors: Dict[str, str] = {}

        # Get execution order (topological sort)
        nodes = plan.get_execution_order()

        for node in nodes:
            try:
                await self._execute_node(node)
                completed += 1
            except Exception as e:
                failed += 1
                errors[node.id] = str(e)
                node.status = NodeStatus.FAILED
                node.error = str(e)

                if self.on_node_failed:
                    self.on_node_failed(node, str(e))

                log.error(f"Node {node.id} failed: {e}")

                # Skip children of failed nodes
                self._skip_descendants(node)

        return {
            "success": failed == 0,
            "completed": completed,
            "failed": failed,
            "total": len(nodes),
            "outputs": dict(self._node_outputs),
            "errors": errors,
        }

    async def _execute_node(self, node: ActionNode) -> Dict[str, Any]:
        """Execute a single node."""
        node.status = NodeStatus.RUNNING

        if self.on_node_start:
            self.on_node_start(node)

        log.info(f"Executing {node.id}: {node.action_name}")

        # Resolve placeholders in inputs
        resolved_inputs = self._resolve_placeholders(node.inputs)

        # Execute the action
        output = await self._dispatch_action(node.action_name, resolved_inputs)

        # Store output for later placeholder resolution
        self._node_outputs[node.id] = output
        node.output = output
        node.status = NodeStatus.COMPLETED

        if self.on_node_complete:
            self.on_node_complete(node, output)

        log.info(f"Completed {node.id}: {output}")

        return output

    def _resolve_placeholders(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve placeholder references in inputs.

        Replaces $node_id.field with actual values from executed nodes.
        """
        resolved = {}

        for key, value in inputs.items():
            if PlaceholderID.is_placeholder(value):
                placeholder = PlaceholderID.parse(value)

                if placeholder.node_id not in self._node_outputs:
                    raise ExecutionError(
                        "placeholder",
                        "resolve",
                        f"Node {placeholder.node_id} not yet executed for placeholder {value}",
                    )

                node_output = self._node_outputs[placeholder.node_id]
                resolved_value = node_output.get(placeholder.output_field)

                if resolved_value is None:
                    raise ExecutionError(
                        "placeholder",
                        "resolve",
                        f"Field {placeholder.output_field} not found in output of {placeholder.node_id}",
                    )

                resolved[key] = resolved_value
            else:
                resolved[key] = value

        return resolved

    async def _dispatch_action(
        self,
        action_name: str,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Dispatch an action to the appropriate handler.

        Args:
            action_name: Name of the action
            inputs: Resolved input parameters

        Returns:
            Output dict with at least 'id' field
        """
        handlers = {
            "create_document": self._action_create_document,
            "add_chapter": self._action_add_chapter,
            "add_section": self._action_add_section,
            "write_page": self._action_write_page,
            "edit_page": self._action_edit_page,
            "delete_page": self._action_delete_page,
        }

        handler = handlers.get(action_name)
        if not handler:
            raise ExecutionError(
                "dispatcher",
                action_name,
                f"Unknown action: {action_name}",
            )

        return await handler(inputs)

    async def _action_create_document(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new document."""
        doc = await self.doc_store.create_document(
            title=inputs.get("title", "Untitled"),
            author=inputs.get("author"),
            metadata=inputs.get("metadata"),
        )
        return {"id": str(doc.id), "title": doc.title}

    async def _action_add_chapter(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Add a chapter to a document."""
        document_id = UUID(inputs["document_id"])
        chapter = await self.doc_store.create_chapter(
            document_id=document_id,
            title=inputs.get("title", "Chapter"),
            order_index=inputs.get("order_index"),
            summary=inputs.get("summary") or inputs.get("description"),
        )
        return {"id": str(chapter.id), "title": chapter.title}

    async def _action_add_section(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Add a section to a chapter."""
        chapter_id = UUID(inputs["chapter_id"])
        section = await self.doc_store.create_section(
            chapter_id=chapter_id,
            title=inputs.get("title", "Section"),
            order_index=inputs.get("order_index"),
        )
        return {"id": str(section.id), "title": section.title}

    async def _action_write_page(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Write a page in a section."""
        section_id = UUID(inputs["section_id"])

        # Get content from various possible input fields
        content = (
            inputs.get("content")
            or inputs.get("content_outline")
            or inputs.get("text")
            or ""
        )

        page = await self.doc_store.create_page(
            section_id=section_id,
            content=content,
            page_number=inputs.get("page_number"),
        )
        return {"id": str(page.id), "page_number": page.page_number}

    async def _action_edit_page(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Edit an existing page."""
        page_id = UUID(inputs["page_id"])
        content = inputs.get("content", "")

        page = await self.doc_store.update_page(
            page_id=page_id,
            content=content,
        )

        if page is None:
            raise ExecutionError("edit_page", "update", f"Page {page_id} not found")

        return {"id": str(page.id), "page_number": page.page_number}

    async def _action_delete_page(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a page."""
        page_id = UUID(inputs["page_id"])

        success = await self.doc_store.delete_page(page_id)

        if not success:
            raise ExecutionError("delete_page", "delete", f"Page {page_id} not found")

        return {"id": str(page_id), "deleted": True}

    def _skip_descendants(self, node: ActionNode) -> None:
        """Mark all descendants of a node as skipped."""
        for child in node.children:
            child.status = NodeStatus.SKIPPED
            child.error = f"Skipped due to parent failure: {node.id}"
            self._skip_descendants(child)


async def execute_plan(
    plan: ActionPlan,
    doc_store: DocumentStore,
    on_progress: Optional[Callable[[str, ActionNode], None]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to execute a plan.

    Args:
        plan: The ActionPlan to execute
        doc_store: Connected DocumentStore
        on_progress: Optional callback(status, node) for progress

    Returns:
        Execution result dict
    """

    def on_start(node: ActionNode):
        if on_progress:
            on_progress("start", node)

    def on_complete(node: ActionNode, output: Dict[str, Any]):
        if on_progress:
            on_progress("complete", node)

    def on_failed(node: ActionNode, error: str):
        if on_progress:
            on_progress("failed", node)

    executor = PlanExecutor(
        doc_store=doc_store,
        on_node_start=on_start,
        on_node_complete=on_complete,
        on_node_failed=on_failed,
    )

    return await executor.execute(plan)
