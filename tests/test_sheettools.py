"""
Tests for Excel-focused agentic tooling in officeplane.sheettools.
"""

import shutil
import tempfile
from pathlib import Path

from officeplane.sheettools import (
    ActionStep,
    ActionType,
    CellModifier,
    PlanExecutor,
    PlanPhase,
    SheetReader,
    SpreadsheetEditor,
    SpreadsheetPlan,
    TableBuilder,
    plan_from_dict,
)


def _mk_temp_dir() -> Path:
    return Path(tempfile.mkdtemp())


class TestSpreadsheetEditor:
    def test_create_save_and_reopen(self):
        temp_dir = _mk_temp_dir()
        try:
            path = temp_dir / "book.xlsx"
            with SpreadsheetEditor(path, create_if_missing=True) as editor:
                editor.rename_sheet("Sheet1", "Summary")
                editor.set_cell("Summary", 1, 1, "Metric")
                editor.set_cell("Summary", 1, 2, "Value")
                editor.set_cell("Summary", 2, 1, "Revenue")
                editor.set_cell("Summary", 2, 2, 125000)
                editor.set_formula("Summary", 3, 2, "=SUM(B2:B2)")
                editor.add_sheet("Data")
                editor.append_row("Data", ["Month", "Revenue"])
                editor.append_row("Data", ["Jan", 125000])

            assert path.exists()

            with SpreadsheetEditor(path) as editor:
                sheets = editor.list_sheets().unwrap()
                assert sheets == ["Summary", "Data"]
                b2 = editor.get_cell("Summary", 2, 2).unwrap()
                assert b2.value == 125000
                b3 = editor.get_cell("Summary", 3, 2).unwrap()
                assert b3.formula == "SUM(B2:B2)"
        finally:
            shutil.rmtree(temp_dir)

    def test_transaction_rollback(self):
        temp_dir = _mk_temp_dir()
        try:
            path = temp_dir / "rollback.xlsx"
            with SpreadsheetEditor(path, create_if_missing=True) as editor:
                editor.rename_sheet("Sheet1", "SheetA")
                editor.set_cell("SheetA", 1, 1, "before")
                initial = editor.get_cell("SheetA", 1, 1).unwrap().value
                assert initial == "before"

                try:
                    with editor.transaction():
                        editor.set_cell("SheetA", 1, 1, "after")
                        raise ValueError("force rollback")
                except ValueError:
                    pass

                value = editor.get_cell("SheetA", 1, 1).unwrap().value
                assert value == "before"
        finally:
            shutil.rmtree(temp_dir)


class TestOperations:
    def test_sheet_reader_modifier_and_tables(self):
        temp_dir = _mk_temp_dir()
        try:
            path = temp_dir / "ops.xlsx"
            with SpreadsheetEditor(path, create_if_missing=True) as editor:
                editor.rename_sheet("Sheet1", "SheetOps")
                modifier = CellModifier(editor)
                reader = SheetReader(editor)
                tables = TableBuilder(editor)

                modifier.set_values("SheetOps", "A1", [["Name", "Amount"], ["Alice", 10], ["Bob", 20]])
                summary = reader.get_sheet_summary("SheetOps").unwrap()
                assert summary.max_row == 3
                assert summary.max_col == 2

                replaced = modifier.replace_in_sheet("SheetOps", "Alice", "Alicia").unwrap()
                assert replaced == 1
                assert editor.get_cell("SheetOps", 2, 1).unwrap().value == "Alicia"

                table_meta = tables.create_table(
                    "SheetOps",
                    "D1",
                    headers=["Metric", "Value"],
                    rows=[["Total", 30]],
                ).unwrap()
                assert table_meta["end_col"] == 5

                total_row = tables.add_totals_row(
                    "SheetOps",
                    label_column="D",
                    value_column="E",
                    start_row=2,
                    end_row=2,
                ).unwrap()
                assert total_row == 3
                e3 = editor.get_cell("SheetOps", 3, 5).unwrap()
                assert e3.formula == "SUM(E2:E2)"
        finally:
            shutil.rmtree(temp_dir)


class TestSpreadsheetPlan:
    def test_execute_plan(self):
        temp_dir = _mk_temp_dir()
        try:
            path = temp_dir / "plan.xlsx"
            with SpreadsheetEditor(path, create_if_missing=True) as editor:
                plan = (
                    SpreadsheetPlan("Build Sales Sheet")
                    .add_sheet("Sales")
                    .set_cell("Sales", "A1", "Month")
                    .set_cell("Sales", "B1", "Revenue")
                    .append_row("Sales", ["Jan", 100])
                    .append_row("Sales", ["Feb", 120])
                    .set_formula("Sales", "B4", "=SUM(B2:B3)")
                )

                executor = PlanExecutor(editor)
                result = executor.execute(plan)
                assert result.is_ok()
                executed = result.unwrap()
                assert executed.phase == PlanPhase.COMPLETED

                cell = editor.get_cell("Sales", 4, 2).unwrap()
                assert cell.formula == "SUM(B2:B3)"
        finally:
            shutil.rmtree(temp_dir)

    def test_validation_warnings(self):
        temp_dir = _mk_temp_dir()
        try:
            path = temp_dir / "validate.xlsx"
            with SpreadsheetEditor(path, create_if_missing=True) as editor:
                plan = SpreadsheetPlan("Invalid").add_step(
                    ActionStep(
                        action=ActionType.SET_CELL,
                        params={"sheet": "Sheet1", "value": 10},
                    )
                )
                warnings = PlanExecutor(editor).validate(plan).unwrap()
                assert any("requires 'cell'" in warning for warning in warnings)
        finally:
            shutil.rmtree(temp_dir)

    def test_plan_from_dict(self):
        plan_data = {
            "name": "From Dict",
            "steps": [
                {"action": "add_sheet", "params": {"name": "Data"}},
                {"action": "set_cell", "params": {"sheet": "Data", "cell": "A1", "value": "KPI"}},
            ],
        }
        result = plan_from_dict(plan_data)
        assert result.is_ok()
        plan = result.unwrap()
        assert plan.name == "From Dict"
        assert len(plan.steps) == 2
