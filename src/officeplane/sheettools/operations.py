"""
High-level spreadsheet operations for agent workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from officeplane.doctools.result import (
    DocError,
    Err,
    ErrorCode,
    Ok,
    Result,
)
from officeplane.sheettools.editor import (
    SpreadsheetEditor,
    cell_ref_to_indices,
    column_to_index,
)


@dataclass
class SheetSummary:
    """Compact sheet-level metadata."""

    name: str
    max_row: int
    max_col: int
    cell_count: int


class SheetReader:
    """Read workbook and sheet structure."""

    def __init__(self, editor: SpreadsheetEditor):
        self.editor = editor

    def list_sheets(self) -> Result[List[str]]:
        return self.editor.list_sheets()

    def get_sheet_summary(self, sheet: str) -> Result[SheetSummary]:
        stats_result = self.editor.get_stats()
        if stats_result.is_err():
            return Err(stats_result.unwrap_err())

        stats = stats_result.unwrap()
        sheet_stats = stats["sheets"].get(sheet)
        if not sheet_stats:
            return Err(DocError.element_not_found("sheet", sheet, "workbook"))

        return Ok(
            SheetSummary(
                name=sheet,
                max_row=sheet_stats["max_row"],
                max_col=sheet_stats["max_col"],
                cell_count=sheet_stats["cells"],
            )
        )

    def get_used_range(self, sheet: str) -> Result[Dict[str, int]]:
        summary_result = self.get_sheet_summary(sheet)
        if summary_result.is_err():
            return Err(summary_result.unwrap_err())
        summary = summary_result.unwrap()
        return Ok(
            {
                "start_row": 1 if summary.max_row > 0 else 0,
                "start_col": 1 if summary.max_col > 0 else 0,
                "end_row": summary.max_row,
                "end_col": summary.max_col,
            }
        )

    def get_row(
        self,
        sheet: str,
        row: int,
        start_col: int = 1,
        end_col: Optional[int] = None,
    ) -> Result[List[Any]]:
        if row < 1:
            return Err(DocError.invalid_position(row, "row >= 1"))
        if start_col < 1:
            return Err(DocError.invalid_position(start_col, "start_col >= 1"))

        if end_col is None:
            summary_result = self.get_sheet_summary(sheet)
            if summary_result.is_err():
                return Err(summary_result.unwrap_err())
            end_col = max(start_col, summary_result.unwrap().max_col)
        if end_col < start_col:
            return Err(DocError(code=ErrorCode.INVALID_RANGE, message="end_col must be >= start_col"))

        range_result = self.editor.get_range(sheet, row, start_col, row, end_col)
        if range_result.is_err():
            return Err(range_result.unwrap_err())
        return Ok(range_result.unwrap()[0])

    def get_column(
        self,
        sheet: str,
        column: int,
        start_row: int = 1,
        end_row: Optional[int] = None,
    ) -> Result[List[Any]]:
        if column < 1:
            return Err(DocError.invalid_position(column, "column >= 1"))
        if start_row < 1:
            return Err(DocError.invalid_position(start_row, "start_row >= 1"))

        if end_row is None:
            summary_result = self.get_sheet_summary(sheet)
            if summary_result.is_err():
                return Err(summary_result.unwrap_err())
            end_row = max(start_row, summary_result.unwrap().max_row)
        if end_row < start_row:
            return Err(DocError(code=ErrorCode.INVALID_RANGE, message="end_row must be >= start_row"))

        range_result = self.editor.get_range(sheet, start_row, column, end_row, column)
        if range_result.is_err():
            return Err(range_result.unwrap_err())
        return Ok([row[0] for row in range_result.unwrap()])


class CellModifier:
    """Semantic cell/range modifications."""

    def __init__(self, editor: SpreadsheetEditor):
        self.editor = editor

    def set_values(self, sheet: str, start_cell: str, data: List[List[Any]]) -> Result[int]:
        try:
            start_row, start_col = cell_ref_to_indices(start_cell)
        except ValueError as exc:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message=str(exc), cause=exc))
        return self.editor.set_range(sheet, start_row, start_col, data)

    def set_value(self, sheet: str, cell: str, value: Any) -> Result[Any]:
        try:
            row, col = cell_ref_to_indices(cell)
        except ValueError as exc:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message=str(exc), cause=exc))
        result = self.editor.set_cell(sheet, row, col, value)
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(result.unwrap())

    def set_formula(self, sheet: str, cell: str, formula: str) -> Result[Any]:
        try:
            row, col = cell_ref_to_indices(cell)
        except ValueError as exc:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message=str(exc), cause=exc))
        result = self.editor.set_formula(sheet, row, col, formula)
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(result.unwrap())

    def clear_values(self, sheet: str, start_cell: str, end_cell: str) -> Result[int]:
        try:
            start_row, start_col = cell_ref_to_indices(start_cell)
            end_row, end_col = cell_ref_to_indices(end_cell)
        except ValueError as exc:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message=str(exc), cause=exc))
        return self.editor.clear_range(sheet, start_row, start_col, end_row, end_col)

    def replace_in_sheet(self, sheet: str, old_text: str, new_text: str) -> Result[int]:
        return self.editor.replace_text(sheet, old_text, new_text)

    def append_records(
        self,
        sheet: str,
        records: List[List[Any]],
        start_col: Union[int, str] = 1,
    ) -> Result[List[int]]:
        if isinstance(start_col, str):
            try:
                start_col_idx = column_to_index(start_col)
            except ValueError as exc:
                return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message=str(exc), cause=exc))
        else:
            start_col_idx = start_col

        if start_col_idx < 1:
            return Err(DocError.invalid_position(start_col_idx, "start_col >= 1"))

        appended_rows: List[int] = []
        for record in records:
            row_result = self.editor.append_row(sheet, record, start_col=start_col_idx)
            if row_result.is_err():
                return Err(row_result.unwrap_err())
            appended_rows.append(row_result.unwrap())
        return Ok(appended_rows)


class TableBuilder:
    """Helpers for header/data style table construction."""

    def __init__(self, editor: SpreadsheetEditor):
        self.editor = editor

    def create_table(
        self,
        sheet: str,
        start_cell: str,
        headers: List[str],
        rows: List[List[Any]],
    ) -> Result[Dict[str, Any]]:
        if not headers:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message="headers cannot be empty"))
        try:
            start_row, start_col = cell_ref_to_indices(start_cell)
        except ValueError as exc:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message=str(exc), cause=exc))

        data = [headers] + rows
        set_result = self.editor.set_range(sheet, start_row, start_col, data)
        if set_result.is_err():
            return Err(set_result.unwrap_err())

        end_row = start_row + len(data) - 1
        end_col = start_col + len(headers) - 1
        return Ok(
            {
                "sheet": sheet,
                "start_row": start_row,
                "start_col": start_col,
                "end_row": end_row,
                "end_col": end_col,
                "rows_written": len(data),
            }
        )

    def add_totals_row(
        self,
        sheet: str,
        label_column: str,
        value_column: str,
        start_row: int,
        end_row: int,
        label: str = "Total",
    ) -> Result[int]:
        if end_row < start_row:
            return Err(DocError(code=ErrorCode.INVALID_RANGE, message="end_row must be >= start_row"))

        try:
            label_col_idx = column_to_index(label_column)
            value_col_idx = column_to_index(value_column)
        except ValueError as exc:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message=str(exc), cause=exc))

        target_row = end_row + 1
        label_result = self.editor.set_cell(sheet, target_row, label_col_idx, label)
        if label_result.is_err():
            return Err(label_result.unwrap_err())

        formula = f"SUM({value_column}{start_row}:{value_column}{end_row})"
        formula_result = self.editor.set_formula(sheet, target_row, value_col_idx, formula)
        if formula_result.is_err():
            return Err(formula_result.unwrap_err())

        return Ok(target_row)
