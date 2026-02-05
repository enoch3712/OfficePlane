"""
Document manipulation planning and execution system.

Inspired by Claude Code's feature-dev plugin, this module provides
a phased approach to complex document operations:

    Phase 1: Analysis   - Understand document structure
    Phase 2: Planning   - Design the changes
    Phase 3: Validation - Verify plan is safe
    Phase 4: Execution  - Apply changes (with rollback)
    Phase 5: Review     - Verify results

Key concepts:
- DocumentPlan: A plan with multiple ActionSteps
- ActionStep: A single document operation with rollback info
- PlanExecutor: Executes plans with transaction support

Example:
    # Create a plan
    plan = DocumentPlan(
        name="Add chapter with summary table",
        description="Insert Chapter 3 with introduction and summary table",
    )

    # Add steps
    plan.add_step(ActionStep(
        action="add_heading",
        params={"text": "Chapter 3: Results", "level": 1},
    ))
    plan.add_step(ActionStep(
        action="add_paragraph",
        params={"text": "This chapter presents our findings..."},
    ))
    plan.add_step(ActionStep(
        action="add_table",
        params={"data": [["Metric", "Value"], ["Accuracy", "95%"]]},
    ))

    # Execute with rollback on failure
    executor = PlanExecutor(editor)
    result = executor.execute(plan)

    if result.is_err():
        print(f"Failed: {result.unwrap_err()}")
        # Automatic rollback has occurred
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from uuid import uuid4

from officeplane.doctools.result import (
    DocError,
    ErrorCode,
    Err,
    Ok,
    Result,
)
from officeplane.doctools.editor import DocumentEditor


class PlanPhase(Enum):
    """Phases of plan execution."""

    CREATED = auto()      # Plan just created
    ANALYZING = auto()    # Analyzing document structure
    PLANNING = auto()     # Building the action plan
    VALIDATING = auto()   # Validating plan safety
    EXECUTING = auto()    # Applying changes
    REVIEWING = auto()    # Verifying results
    COMPLETED = auto()    # Successfully completed
    FAILED = auto()       # Failed (rolled back)
    CANCELLED = auto()    # Cancelled by user/system


class ActionType(Enum):
    """Types of document actions."""

    # Paragraph actions
    ADD_PARAGRAPH = "add_paragraph"
    INSERT_PARAGRAPH = "insert_paragraph"
    DELETE_PARAGRAPH = "delete_paragraph"
    REPLACE_TEXT = "replace_text"

    # Heading actions
    ADD_HEADING = "add_heading"

    # Table actions
    ADD_TABLE = "add_table"
    FILL_TABLE = "fill_table"
    SET_CELL = "set_cell"

    # Section actions
    INSERT_AFTER_HEADING = "insert_after_heading"
    INSERT_BEFORE_HEADING = "insert_before_heading"
    REPLACE_IN_SECTION = "replace_in_section"
    DELETE_SECTION = "delete_section"
    APPEND_TO_SECTION = "append_to_section"

    # Compound actions
    CREATE_DATA_TABLE = "create_data_table"
    CREATE_KEY_VALUE_TABLE = "create_key_value_table"


@dataclass
class ActionStep:
    """
    A single step in a document manipulation plan.

    Each step represents one atomic operation with:
    - action: What to do (ActionType or string)
    - params: Parameters for the action
    - description: Human-readable description
    - depends_on: Optional list of step IDs this depends on
    """

    action: Union[ActionType, str]
    params: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)

    # Execution state (filled during execution)
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    status: str = "pending"  # pending, running, completed, failed, skipped
    result: Optional[Any] = None
    error: Optional[str] = None
    executed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "action": self.action.value if isinstance(self.action, ActionType) else self.action,
            "params": self.params,
            "description": self.description or self._generate_description(),
            "depends_on": self.depends_on,
            "status": self.status,
        }

    def _generate_description(self) -> str:
        """Generate a human-readable description from action and params."""
        action_str = self.action.value if isinstance(self.action, ActionType) else self.action

        if action_str == "add_paragraph":
            text = self.params.get("text", "")[:50]
            return f"Add paragraph: {text}..."
        elif action_str == "add_heading":
            text = self.params.get("text", "")
            level = self.params.get("level", 1)
            return f"Add heading (level {level}): {text}"
        elif action_str == "add_table":
            rows = self.params.get("rows", 0)
            cols = self.params.get("cols", 0)
            return f"Add table ({rows}x{cols})"
        elif action_str == "replace_text":
            old = self.params.get("old_text", "")[:20]
            new = self.params.get("new_text", "")[:20]
            return f"Replace '{old}' with '{new}'"
        elif action_str == "insert_after_heading":
            heading = self.params.get("heading_text", "")
            return f"Insert content after heading: {heading}"

        return f"{action_str}"


@dataclass
class DocumentPlan:
    """
    A complete plan for document manipulation.

    Plans contain:
    - Metadata (name, description, timestamps)
    - List of ordered ActionSteps
    - Execution state and history
    """

    name: str
    description: str = ""
    steps: List[ActionStep] = field(default_factory=list)

    # Metadata
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Execution state
    phase: PlanPhase = PlanPhase.CREATED
    current_step_index: int = 0
    error: Optional[str] = None

    def add_step(self, step: ActionStep) -> DocumentPlan:
        """Add a step to the plan (chainable)."""
        self.steps.append(step)
        return self

    def add_paragraph(
        self,
        text: str,
        style: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DocumentPlan:
        """Add a 'add_paragraph' step (chainable)."""
        params = {"text": text}
        if style:
            params["style"] = style

        self.steps.append(
            ActionStep(
                action=ActionType.ADD_PARAGRAPH,
                params=params,
                description=description,
            )
        )
        return self

    def add_heading(
        self,
        text: str,
        level: int = 1,
        description: Optional[str] = None,
    ) -> DocumentPlan:
        """Add a 'add_heading' step (chainable)."""
        self.steps.append(
            ActionStep(
                action=ActionType.ADD_HEADING,
                params={"text": text, "level": level},
                description=description,
            )
        )
        return self

    def add_table(
        self,
        data: List[List[str]],
        style: Optional[str] = "Table Grid",
        description: Optional[str] = None,
    ) -> DocumentPlan:
        """Add a 'create_data_table' step (chainable)."""
        self.steps.append(
            ActionStep(
                action=ActionType.CREATE_DATA_TABLE,
                params={"data": data, "style": style},
                description=description,
            )
        )
        return self

    def insert_after(
        self,
        heading_text: str,
        content: Union[str, List[str]],
        style: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DocumentPlan:
        """Add an 'insert_after_heading' step (chainable)."""
        params = {"heading_text": heading_text, "content": content}
        if style:
            params["style"] = style

        self.steps.append(
            ActionStep(
                action=ActionType.INSERT_AFTER_HEADING,
                params=params,
                description=description,
            )
        )
        return self

    def replace_in_section(
        self,
        heading_text: str,
        old_text: str,
        new_text: str,
        description: Optional[str] = None,
    ) -> DocumentPlan:
        """Add a 'replace_in_section' step (chainable)."""
        self.steps.append(
            ActionStep(
                action=ActionType.REPLACE_IN_SECTION,
                params={
                    "heading_text": heading_text,
                    "old_text": old_text,
                    "new_text": new_text,
                },
                description=description,
            )
        )
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serialize plan to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "phase": self.phase.name,
            "step_count": len(self.steps),
            "current_step": self.current_step_index,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize plan to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def summary(self) -> str:
        """Get a human-readable summary of the plan."""
        lines = [
            f"Plan: {self.name}",
            f"Description: {self.description}",
            f"Phase: {self.phase.name}",
            f"Steps: {len(self.steps)}",
            "",
        ]

        for i, step in enumerate(self.steps):
            status_icon = {
                "pending": "[ ]",
                "running": "[~]",
                "completed": "[x]",
                "failed": "[!]",
                "skipped": "[-]",
            }.get(step.status, "[ ]")

            desc = step.description or step._generate_description()
            lines.append(f"  {i + 1}. {status_icon} {desc}")

        return "\n".join(lines)


class PlanExecutor:
    """
    Executes DocumentPlans with transaction support.

    Provides:
    - Phase-based execution
    - Automatic rollback on failure
    - Progress tracking
    - Execution hooks for monitoring
    """

    def __init__(self, editor: DocumentEditor):
        """
        Initialize executor with an open editor.

        Args:
            editor: An open DocumentEditor instance
        """
        self.editor = editor
        self._on_step_start: Optional[Callable[[ActionStep], None]] = None
        self._on_step_complete: Optional[Callable[[ActionStep, Any], None]] = None
        self._on_step_failed: Optional[Callable[[ActionStep, DocError], None]] = None

    def on_step_start(self, callback: Callable[[ActionStep], None]) -> PlanExecutor:
        """Set callback for when a step starts (chainable)."""
        self._on_step_start = callback
        return self

    def on_step_complete(
        self,
        callback: Callable[[ActionStep, Any], None],
    ) -> PlanExecutor:
        """Set callback for when a step completes (chainable)."""
        self._on_step_complete = callback
        return self

    def on_step_failed(
        self,
        callback: Callable[[ActionStep, DocError], None],
    ) -> PlanExecutor:
        """Set callback for when a step fails (chainable)."""
        self._on_step_failed = callback
        return self

    def validate(self, plan: DocumentPlan) -> Result[List[str]]:
        """
        Validate a plan before execution.

        Checks:
        - All actions are recognized
        - Required parameters are present
        - Dependencies are valid

        Returns:
            Result containing list of warning messages (empty if all good)
        """
        plan.phase = PlanPhase.VALIDATING
        warnings: List[str] = []

        step_ids = {s.id for s in plan.steps}

        for i, step in enumerate(plan.steps):
            # Check action is valid
            action = step.action
            if isinstance(action, str):
                try:
                    ActionType(action)
                except ValueError:
                    warnings.append(f"Step {i + 1}: Unknown action '{action}'")

            # Check dependencies
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    warnings.append(
                        f"Step {i + 1}: Dependency '{dep_id}' not found in plan"
                    )

            # Check required params based on action
            action_str = action.value if isinstance(action, ActionType) else action

            if action_str == "add_paragraph" and "text" not in step.params:
                warnings.append(f"Step {i + 1}: 'add_paragraph' requires 'text' param")
            elif action_str == "add_heading" and "text" not in step.params:
                warnings.append(f"Step {i + 1}: 'add_heading' requires 'text' param")
            elif action_str == "insert_after_heading":
                if "heading_text" not in step.params:
                    warnings.append(
                        f"Step {i + 1}: 'insert_after_heading' requires 'heading_text'"
                    )
                if "content" not in step.params:
                    warnings.append(
                        f"Step {i + 1}: 'insert_after_heading' requires 'content'"
                    )

        return Ok(warnings)

    def execute(
        self,
        plan: DocumentPlan,
        dry_run: bool = False,
    ) -> Result[DocumentPlan]:
        """
        Execute a document plan.

        Args:
            plan: The plan to execute
            dry_run: If True, validate but don't execute

        Returns:
            Result containing the updated plan
        """
        # Validate first
        validation_result = self.validate(plan)
        if validation_result.is_err():
            return Err(validation_result.unwrap_err())

        warnings = validation_result.unwrap()
        if warnings:
            # Warnings don't stop execution, but we note them
            plan.error = f"Warnings: {'; '.join(warnings)}"

        if dry_run:
            plan.phase = PlanPhase.VALIDATING
            return Ok(plan)

        # Execute within a transaction
        plan.phase = PlanPhase.EXECUTING
        plan.started_at = datetime.now()

        try:
            with self.editor.transaction() as tx:
                for i, step in enumerate(plan.steps):
                    plan.current_step_index = i
                    step.status = "running"
                    step.executed_at = datetime.now()

                    if self._on_step_start:
                        self._on_step_start(step)

                    result = self._execute_step(step)

                    if result.is_err():
                        step.status = "failed"
                        step.error = str(result.unwrap_err())
                        plan.phase = PlanPhase.FAILED
                        plan.error = step.error

                        if self._on_step_failed:
                            self._on_step_failed(step, result.unwrap_err())

                        # Transaction will rollback automatically
                        raise RuntimeError(f"Step {i + 1} failed: {step.error}")

                    step.status = "completed"
                    step.result = result.unwrap()

                    if self._on_step_complete:
                        self._on_step_complete(step, step.result)

                # All steps completed
                tx.commit()

        except RuntimeError:
            # Plan failed - already marked as FAILED
            return Ok(plan)

        except Exception as e:
            plan.phase = PlanPhase.FAILED
            plan.error = str(e)
            return Err(DocError.from_exception(e, "Executing plan"))

        plan.phase = PlanPhase.COMPLETED
        plan.completed_at = datetime.now()

        return Ok(plan)

    def _execute_step(self, step: ActionStep) -> Result[Any]:
        """Execute a single step."""
        action = step.action
        action_str = action.value if isinstance(action, ActionType) else action
        params = step.params

        # Import operations here to avoid circular import
        from officeplane.doctools.operations import (
            ContentModifier,
            TableBuilder,
        )

        content = ContentModifier(self.editor)
        tables = TableBuilder(self.editor)

        # Map action to operation
        if action_str == ActionType.ADD_PARAGRAPH.value:
            return self.editor.add_paragraph(
                params["text"],
                params.get("style"),
            )

        elif action_str == ActionType.ADD_HEADING.value:
            return self.editor.add_heading(
                params["text"],
                params.get("level", 1),
            )

        elif action_str == ActionType.DELETE_PARAGRAPH.value:
            return self.editor.delete_paragraph(params["index"])

        elif action_str == ActionType.REPLACE_TEXT.value:
            return self.editor.replace_text(
                params["old_text"],
                params["new_text"],
                params.get("paragraph_index"),
            )

        elif action_str == ActionType.ADD_TABLE.value:
            return self.editor.add_table(
                params["rows"],
                params["cols"],
                params.get("style"),
            )

        elif action_str == ActionType.SET_CELL.value:
            return self.editor.set_cell(
                params["table_index"],
                params["row"],
                params["col"],
                params["text"],
            )

        elif action_str == ActionType.INSERT_AFTER_HEADING.value:
            return content.insert_after_heading(
                params["heading_text"],
                params["content"],
                params.get("style"),
            )

        elif action_str == ActionType.INSERT_BEFORE_HEADING.value:
            return content.insert_before_heading(
                params["heading_text"],
                params["content"],
                params.get("style"),
            )

        elif action_str == ActionType.REPLACE_IN_SECTION.value:
            return content.replace_in_section(
                params["heading_text"],
                params["old_text"],
                params["new_text"],
            )

        elif action_str == ActionType.DELETE_SECTION.value:
            return content.delete_section_content(
                params["heading_text"],
                params.get("keep_heading", True),
            )

        elif action_str == ActionType.APPEND_TO_SECTION.value:
            return content.append_to_section(
                params["heading_text"],
                params["content"],
                params.get("style"),
            )

        elif action_str == ActionType.CREATE_DATA_TABLE.value:
            return tables.create_data_table(
                params["data"],
                params.get("has_header", True),
                params.get("style", "Table Grid"),
            )

        elif action_str == ActionType.CREATE_KEY_VALUE_TABLE.value:
            return tables.create_key_value_table(
                params["data"],
                params.get("key_header", "Property"),
                params.get("value_header", "Value"),
                params.get("style", "Table Grid"),
            )

        else:
            return Err(
                DocError(
                    code=ErrorCode.INVALID_ARGUMENT,
                    message=f"Unknown action: {action_str}",
                )
            )


# =============================================================================
# Plan Builder Helpers
# =============================================================================


def plan_from_dict(data: Dict[str, Any]) -> Result[DocumentPlan]:
    """
    Create a DocumentPlan from a dictionary.

    Useful for loading plans from JSON or creating plans programmatically.

    Args:
        data: Dictionary with plan data

    Returns:
        Result containing DocumentPlan
    """
    try:
        plan = DocumentPlan(
            name=data.get("name", "Unnamed Plan"),
            description=data.get("description", ""),
        )

        for step_data in data.get("steps", []):
            action = step_data.get("action", "")
            # Try to convert to ActionType if possible
            try:
                action = ActionType(action)
            except ValueError:
                pass  # Keep as string

            step = ActionStep(
                action=action,
                params=step_data.get("params", {}),
                description=step_data.get("description"),
                depends_on=step_data.get("depends_on", []),
            )
            plan.add_step(step)

        return Ok(plan)

    except Exception as e:
        return Err(DocError.from_exception(e, "Creating plan from dict"))


def plan_from_json(json_str: str) -> Result[DocumentPlan]:
    """
    Create a DocumentPlan from a JSON string.

    Args:
        json_str: JSON string with plan data

    Returns:
        Result containing DocumentPlan
    """
    try:
        data = json.loads(json_str)
        return plan_from_dict(data)
    except json.JSONDecodeError as e:
        return Err(
            DocError(
                code=ErrorCode.INVALID_FORMAT,
                message=f"Invalid JSON: {e}",
                cause=e,
            )
        )
