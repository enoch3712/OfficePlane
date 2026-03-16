"""
Excel-focused agentic tooling (parallel to officeplane.doctools).
"""

from officeplane.doctools.result import (
    Result,
    Ok,
    Err,
    DocError,
    ErrorCode,
)
from officeplane.sheettools.editor import (
    SpreadsheetEditor,
    EditSession,
    EditorState,
    CellRef,
    cell_ref_to_indices,
    indices_to_cell_ref,
)
from officeplane.sheettools.operations import (
    SheetReader,
    CellModifier,
    TableBuilder,
    SheetSummary,
)
from officeplane.sheettools.planner import (
    SpreadsheetPlan,
    PlanPhase,
    ActionType,
    ActionStep,
    PlanExecutor,
    plan_from_dict,
    plan_from_json,
)

__all__ = [
    "Result",
    "Ok",
    "Err",
    "DocError",
    "ErrorCode",
    "SpreadsheetEditor",
    "EditSession",
    "EditorState",
    "CellRef",
    "cell_ref_to_indices",
    "indices_to_cell_ref",
    "SheetReader",
    "CellModifier",
    "TableBuilder",
    "SheetSummary",
    "SpreadsheetPlan",
    "PlanPhase",
    "ActionType",
    "ActionStep",
    "PlanExecutor",
    "plan_from_dict",
    "plan_from_json",
]
