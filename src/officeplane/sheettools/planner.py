"""
Spreadsheet planning and execution for agentic workflows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import uuid4

from officeplane.doctools.result import (
    DocError,
    Err,
    ErrorCode,
    Ok,
    Result,
)
from officeplane.sheettools.editor import SpreadsheetEditor, cell_ref_to_indices
from officeplane.sheettools.operations import CellModifier, TableBuilder


class PlanPhase(Enum):
    """Phases of spreadsheet plan execution."""

    CREATED = auto()
    VALIDATING = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class ActionType(Enum):
    """Supported spreadsheet actions."""

    ADD_SHEET = "add_sheet"
    RENAME_SHEET = "rename_sheet"
    DELETE_SHEET = "delete_sheet"
    SET_CELL = "set_cell"
    SET_FORMULA = "set_formula"
    SET_RANGE = "set_range"
    APPEND_ROW = "append_row"
    CLEAR_RANGE = "clear_range"
    REPLACE_TEXT = "replace_text"
    CREATE_TABLE = "create_table"
    ADD_TOTALS_ROW = "add_totals_row"


@dataclass
class ActionStep:
    """Single spreadsheet operation in a plan."""

    action: Union[ActionType, str]
    params: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    executed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        action_str = self.action.value if isinstance(self.action, ActionType) else self.action
        return {
            "id": self.id,
            "action": action_str,
            "params": self.params,
            "description": self.description or self._generate_description(),
            "depends_on": self.depends_on,
            "status": self.status,
        }

    def _generate_description(self) -> str:
        action_str = self.action.value if isinstance(self.action, ActionType) else self.action
        params = self.params
        if action_str == "add_sheet":
            return f"Add sheet '{params.get('name', '')}'"
        if action_str == "set_cell":
            return (
                f"Set {params.get('sheet', '')}!{params.get('cell', '')} = "
                f"{params.get('value', '')!r}"
            )
        if action_str == "set_formula":
            return (
                f"Set formula {params.get('sheet', '')}!{params.get('cell', '')} = "
                f"{params.get('formula', '')}"
            )
        if action_str == "append_row":
            return f"Append row to {params.get('sheet', '')}"
        if action_str == "create_table":
            rows = len(params.get("rows", []))
            cols = len(params.get("headers", []))
            return f"Create table in {params.get('sheet', '')} ({rows + 1}x{cols})"
        return action_str


@dataclass
class SpreadsheetPlan:
    """Plan with ordered spreadsheet actions."""

    name: str
    description: str = ""
    steps: List[ActionStep] = field(default_factory=list)

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    phase: PlanPhase = PlanPhase.CREATED
    current_step_index: int = 0
    error: Optional[str] = None

    def add_step(self, step: ActionStep) -> "SpreadsheetPlan":
        self.steps.append(step)
        return self

    def add_sheet(self, name: str, description: Optional[str] = None) -> "SpreadsheetPlan":
        return self.add_step(
            ActionStep(
                action=ActionType.ADD_SHEET,
                params={"name": name},
                description=description,
            )
        )

    def set_cell(
        self,
        sheet: str,
        cell: str,
        value: Any,
        description: Optional[str] = None,
    ) -> "SpreadsheetPlan":
        return self.add_step(
            ActionStep(
                action=ActionType.SET_CELL,
                params={"sheet": sheet, "cell": cell, "value": value},
                description=description,
            )
        )

    def set_formula(
        self,
        sheet: str,
        cell: str,
        formula: str,
        description: Optional[str] = None,
    ) -> "SpreadsheetPlan":
        return self.add_step(
            ActionStep(
                action=ActionType.SET_FORMULA,
                params={"sheet": sheet, "cell": cell, "formula": formula},
                description=description,
            )
        )

    def append_row(
        self,
        sheet: str,
        values: List[Any],
        start_col: int = 1,
        description: Optional[str] = None,
    ) -> "SpreadsheetPlan":
        return self.add_step(
            ActionStep(
                action=ActionType.APPEND_ROW,
                params={"sheet": sheet, "values": values, "start_col": start_col},
                description=description,
            )
        )

    def create_table(
        self,
        sheet: str,
        start_cell: str,
        headers: List[str],
        rows: List[List[Any]],
        description: Optional[str] = None,
    ) -> "SpreadsheetPlan":
        return self.add_step(
            ActionStep(
                action=ActionType.CREATE_TABLE,
                params={
                    "sheet": sheet,
                    "start_cell": start_cell,
                    "headers": headers,
                    "rows": rows,
                },
                description=description,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "phase": self.phase.name,
            "step_count": len(self.steps),
            "current_step": self.current_step_index,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at.isoformat(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def summary(self) -> str:
        lines = [
            f"Plan: {self.name}",
            f"Description: {self.description}",
            f"Phase: {self.phase.name}",
            f"Steps: {len(self.steps)}",
            "",
        ]
        for i, step in enumerate(self.steps, start=1):
            icon = {
                "pending": "[ ]",
                "running": "[~]",
                "completed": "[x]",
                "failed": "[!]",
                "skipped": "[-]",
            }.get(step.status, "[ ]")
            lines.append(f"  {i}. {icon} {step.description or step._generate_description()}")
        return "\n".join(lines)


class PlanExecutor:
    """Execute SpreadsheetPlan with transaction rollback on failure."""

    def __init__(self, editor: SpreadsheetEditor):
        self.editor = editor
        self._on_step_start: Optional[Callable[[ActionStep], None]] = None
        self._on_step_complete: Optional[Callable[[ActionStep, Any], None]] = None
        self._on_step_failed: Optional[Callable[[ActionStep, DocError], None]] = None

    def on_step_start(self, callback: Callable[[ActionStep], None]) -> "PlanExecutor":
        self._on_step_start = callback
        return self

    def on_step_complete(self, callback: Callable[[ActionStep, Any], None]) -> "PlanExecutor":
        self._on_step_complete = callback
        return self

    def on_step_failed(self, callback: Callable[[ActionStep, DocError], None]) -> "PlanExecutor":
        self._on_step_failed = callback
        return self

    def validate(self, plan: SpreadsheetPlan) -> Result[List[str]]:
        plan.phase = PlanPhase.VALIDATING
        warnings: List[str] = []
        step_ids = {step.id for step in plan.steps}

        required_params: Dict[str, List[str]] = {
            ActionType.ADD_SHEET.value: ["name"],
            ActionType.RENAME_SHEET.value: ["old_name", "new_name"],
            ActionType.DELETE_SHEET.value: ["name"],
            ActionType.SET_CELL.value: ["sheet", "cell", "value"],
            ActionType.SET_FORMULA.value: ["sheet", "cell", "formula"],
            ActionType.SET_RANGE.value: ["sheet", "start_cell", "values"],
            ActionType.APPEND_ROW.value: ["sheet", "values"],
            ActionType.CLEAR_RANGE.value: ["sheet", "start_cell", "end_cell"],
            ActionType.REPLACE_TEXT.value: ["sheet", "old_text", "new_text"],
            ActionType.CREATE_TABLE.value: ["sheet", "start_cell", "headers", "rows"],
            ActionType.ADD_TOTALS_ROW.value: [
                "sheet",
                "label_column",
                "value_column",
                "start_row",
                "end_row",
            ],
        }

        for i, step in enumerate(plan.steps, start=1):
            action_str = step.action.value if isinstance(step.action, ActionType) else step.action
            if action_str not in {item.value for item in ActionType}:
                warnings.append(f"Step {i}: Unknown action '{action_str}'")
                continue
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    warnings.append(f"Step {i}: Dependency '{dep_id}' not found")
            for param in required_params.get(action_str, []):
                if param not in step.params:
                    warnings.append(f"Step {i}: '{action_str}' requires '{param}'")

            if action_str in (ActionType.SET_CELL.value, ActionType.SET_FORMULA.value):
                cell = step.params.get("cell")
                if isinstance(cell, str):
                    try:
                        cell_ref_to_indices(cell)
                    except ValueError:
                        warnings.append(f"Step {i}: Invalid cell reference '{cell}'")

        return Ok(warnings)

    def execute(self, plan: SpreadsheetPlan, dry_run: bool = False) -> Result[SpreadsheetPlan]:
        validation = self.validate(plan)
        if validation.is_err():
            return Err(validation.unwrap_err())

        warnings = validation.unwrap()
        if warnings:
            plan.error = f"Warnings: {'; '.join(warnings)}"
        if dry_run:
            return Ok(plan)

        plan.phase = PlanPhase.EXECUTING
        plan.started_at = datetime.now()

        try:
            with self.editor.transaction() as tx:
                for idx, step in enumerate(plan.steps):
                    plan.current_step_index = idx
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
                        raise RuntimeError(f"Step {idx + 1} failed: {step.error}")

                    step.status = "completed"
                    step.result = result.unwrap()
                    if self._on_step_complete:
                        self._on_step_complete(step, step.result)

                tx.commit()
        except RuntimeError:
            return Ok(plan)
        except Exception as exc:
            plan.phase = PlanPhase.FAILED
            plan.error = str(exc)
            return Err(DocError.from_exception(exc, "Executing spreadsheet plan"))

        plan.phase = PlanPhase.COMPLETED
        plan.completed_at = datetime.now()
        return Ok(plan)

    def _execute_step(self, step: ActionStep) -> Result[Any]:
        action_str = step.action.value if isinstance(step.action, ActionType) else step.action
        params = step.params
        modifier = CellModifier(self.editor)
        tables = TableBuilder(self.editor)

        if action_str == ActionType.ADD_SHEET.value:
            return self.editor.add_sheet(params["name"])
        if action_str == ActionType.RENAME_SHEET.value:
            return self.editor.rename_sheet(params["old_name"], params["new_name"])
        if action_str == ActionType.DELETE_SHEET.value:
            return self.editor.delete_sheet(params["name"])
        if action_str == ActionType.SET_CELL.value:
            return modifier.set_value(params["sheet"], params["cell"], params["value"])
        if action_str == ActionType.SET_FORMULA.value:
            return modifier.set_formula(params["sheet"], params["cell"], params["formula"])
        if action_str == ActionType.SET_RANGE.value:
            return modifier.set_values(params["sheet"], params["start_cell"], params["values"])
        if action_str == ActionType.APPEND_ROW.value:
            return self.editor.append_row(
                params["sheet"],
                params["values"],
                start_col=params.get("start_col", 1),
            )
        if action_str == ActionType.CLEAR_RANGE.value:
            return modifier.clear_values(params["sheet"], params["start_cell"], params["end_cell"])
        if action_str == ActionType.REPLACE_TEXT.value:
            return modifier.replace_in_sheet(params["sheet"], params["old_text"], params["new_text"])
        if action_str == ActionType.CREATE_TABLE.value:
            return tables.create_table(
                params["sheet"],
                params["start_cell"],
                params["headers"],
                params["rows"],
            )
        if action_str == ActionType.ADD_TOTALS_ROW.value:
            return tables.add_totals_row(
                params["sheet"],
                params["label_column"],
                params["value_column"],
                params["start_row"],
                params["end_row"],
                label=params.get("label", "Total"),
            )

        return Err(
            DocError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"Unknown action: {action_str}",
            )
        )


def plan_from_dict(data: Dict[str, Any]) -> Result[SpreadsheetPlan]:
    """Build SpreadsheetPlan from dictionary payload."""
    try:
        plan = SpreadsheetPlan(
            name=data.get("name", "Unnamed Spreadsheet Plan"),
            description=data.get("description", ""),
        )
        for step_data in data.get("steps", []):
            action: Union[ActionType, str] = step_data.get("action", "")
            try:
                action = ActionType(action)
            except ValueError:
                pass
            step = ActionStep(
                action=action,
                params=step_data.get("params", {}),
                description=step_data.get("description"),
                depends_on=step_data.get("depends_on", []),
            )
            plan.add_step(step)
        return Ok(plan)
    except Exception as exc:
        return Err(DocError.from_exception(exc, "Creating spreadsheet plan from dict"))


def plan_from_json(json_str: str) -> Result[SpreadsheetPlan]:
    """Build SpreadsheetPlan from JSON string."""
    try:
        payload = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return Err(
            DocError(
                code=ErrorCode.INVALID_FORMAT,
                message=f"Invalid JSON: {exc}",
                cause=exc,
            )
        )
    return plan_from_dict(payload)
