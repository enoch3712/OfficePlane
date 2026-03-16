"""
SpreadsheetEditor - dependency-free Excel (.xlsx) editing with transactions.

This module mirrors the doctools editing pattern for spreadsheets:
- Open once, perform many operations, save once
- Structured Result types (Ok/Err)
- Transaction support with rollback
"""

from __future__ import annotations

import re
import zipfile
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET

from officeplane.doctools.result import (
    DocError,
    Err,
    ErrorCode,
    Ok,
    Result,
)


NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"

CELL_REF_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")

ET.register_namespace("", NS_MAIN)
ET.register_namespace("r", NS_DOC_REL)


def _qname(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def column_to_index(column: str) -> int:
    """Convert Excel column label (A, B, AA) to 1-based index."""
    col = column.strip().upper()
    if not col or not col.isalpha():
        raise ValueError(f"Invalid column label: {column}")
    result = 0
    for ch in col:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result


def index_to_column(index: int) -> str:
    """Convert 1-based column index to Excel label."""
    if index < 1:
        raise ValueError(f"Column index must be >= 1, got {index}")
    out: List[str] = []
    n = index
    while n > 0:
        n -= 1
        out.append(chr(ord("A") + (n % 26)))
        n //= 26
    return "".join(reversed(out))


def cell_ref_to_indices(cell_ref: str) -> Tuple[int, int]:
    """Convert A1 notation into (row, col), both 1-based."""
    match = CELL_REF_RE.match(cell_ref.strip().upper())
    if not match:
        raise ValueError(f"Invalid cell reference: {cell_ref}")
    col_label, row_str = match.groups()
    row = int(row_str)
    col = column_to_index(col_label)
    return row, col


def indices_to_cell_ref(row: int, col: int) -> str:
    """Convert (row, col) 1-based into A1 notation."""
    if row < 1 or col < 1:
        raise ValueError(f"Row/col must be >= 1, got row={row}, col={col}")
    return f"{index_to_column(col)}{row}"


def _parse_number(value: str) -> Union[int, float, str]:
    try:
        if "." not in value and "e" not in value.lower():
            return int(value)
        return float(value)
    except (ValueError, TypeError):
        return value


@dataclass
class CellValue:
    """Internal cell representation."""

    value: Any = None
    formula: Optional[str] = None


@dataclass
class CellRef:
    """External cell reference with metadata."""

    sheet: str
    row: int
    col: int
    cell: str
    value: Any = None
    formula: Optional[str] = None


@dataclass
class SheetData:
    """Internal representation of a worksheet."""

    name: str
    cells: Dict[Tuple[int, int], CellValue] = field(default_factory=dict)

    def dimensions(self) -> Tuple[int, int]:
        """Return (max_row, max_col) for populated cells."""
        if not self.cells:
            return 0, 0
        max_row = max(r for r, _ in self.cells)
        max_col = max(c for _, c in self.cells)
        return max_row, max_col


@dataclass
class WorkbookData:
    """Workbook with ordered sheets."""

    sheets: OrderedDict[str, SheetData] = field(default_factory=OrderedDict)


class EditorState(Enum):
    """Spreadsheet editor state."""

    CLOSED = auto()
    OPEN = auto()
    MODIFIED = auto()
    ERROR = auto()


class EditSession:
    """Transaction session for spreadsheet edits."""

    def __init__(self, editor: "SpreadsheetEditor"):
        self.editor = editor
        self._backup: Optional[WorkbookData] = None
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "EditSession":
        if self.editor._workbook is None:
            raise ValueError("Editor must be open to start transaction")
        self._backup = deepcopy(self.editor._workbook)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self.rollback()
            return False
        if not self.committed and not self.rolled_back:
            self.commit()
        return False

    def commit(self) -> Result[None]:
        if self.rolled_back:
            return Err(
                DocError(
                    code=ErrorCode.TRANSACTION_FAILED,
                    message="Cannot commit - transaction was rolled back",
                )
            )
        self.committed = True
        return Ok(None)

    def rollback(self) -> Result[None]:
        if self.committed:
            return Err(
                DocError(
                    code=ErrorCode.ROLLBACK_FAILED,
                    message="Cannot rollback - transaction was committed",
                )
            )
        if self._backup is None:
            return Err(
                DocError(
                    code=ErrorCode.ROLLBACK_FAILED,
                    message="No backup available for rollback",
                )
            )
        self.editor._workbook = deepcopy(self._backup)
        self.rolled_back = True
        return Ok(None)


class SpreadsheetEditor:
    """
    Excel editor with batch operations, transaction support, and Result types.

    The implementation reads/writes OOXML .xlsx directly using stdlib XML/ZIP.
    """

    def __init__(
        self,
        path: Union[str, Path],
        auto_save: bool = True,
        create_if_missing: bool = False,
    ):
        self.path = Path(path)
        self.auto_save = auto_save
        self.create_if_missing = create_if_missing

        self._workbook: Optional[WorkbookData] = None
        self._state = EditorState.CLOSED
        self._current_session: Optional[EditSession] = None
        self._operation_count = 0

    @property
    def state(self) -> EditorState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state in (EditorState.OPEN, EditorState.MODIFIED)

    @property
    def is_modified(self) -> bool:
        return self._state == EditorState.MODIFIED

    def __enter__(self) -> "SpreadsheetEditor":
        result = self.open()
        if result.is_err():
            raise RuntimeError(f"Failed to open workbook: {result.unwrap_err()}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None and self.auto_save and self.is_modified:
            self.save()
        self.close()
        return False

    def open(self) -> Result[None]:
        """Open workbook from disk or create a new one."""
        if self._state != EditorState.CLOSED:
            return Err(
                DocError(
                    code=ErrorCode.OPERATION_FAILED,
                    message="Workbook is already open",
                    source_file=str(self.path),
                )
            )

        if self.path.suffix.lower() != ".xlsx":
            return Err(
                DocError(
                    code=ErrorCode.FILE_INVALID_FORMAT,
                    message=f"Unsupported spreadsheet format: {self.path.suffix}",
                    source_file=str(self.path),
                    suggestion="Use a .xlsx file path",
                )
            )

        if not self.path.exists():
            if self.create_if_missing:
                self._workbook = WorkbookData(
                    sheets=OrderedDict({"Sheet1": SheetData(name="Sheet1")})
                )
                self._state = EditorState.MODIFIED
                return Ok(None)
            return Err(DocError.file_not_found(str(self.path)))

        loaded = self._load_xlsx(self.path)
        if loaded.is_err():
            self._state = EditorState.ERROR
            return Err(loaded.unwrap_err())

        self._workbook = loaded.unwrap()
        self._state = EditorState.OPEN
        return Ok(None)

    def close(self) -> None:
        """Close workbook without saving."""
        self._workbook = None
        self._state = EditorState.CLOSED
        self._current_session = None

    def save(self, path: Optional[Union[str, Path]] = None) -> Result[None]:
        """Save workbook to disk."""
        if self._workbook is None:
            return Err(
                DocError(
                    code=ErrorCode.OPERATION_FAILED,
                    message="No workbook is open",
                )
            )

        save_path = Path(path) if path else self.path
        if save_path.suffix.lower() != ".xlsx":
            return Err(
                DocError(
                    code=ErrorCode.FILE_INVALID_FORMAT,
                    message=f"Can only save .xlsx files: {save_path}",
                )
            )

        write_result = self._write_xlsx(save_path, self._workbook)
        if write_result.is_err():
            return Err(write_result.unwrap_err())

        self._state = EditorState.OPEN
        return Ok(None)

    @contextmanager
    def transaction(self) -> Iterator[EditSession]:
        """Start a transaction with rollback support."""
        if self._workbook is None:
            raise ValueError("Editor must be open to start transaction")
        session = EditSession(self)
        self._current_session = session
        try:
            with session:
                yield session
        finally:
            self._current_session = None

    def _mark_modified(self) -> None:
        if self._state == EditorState.OPEN:
            self._state = EditorState.MODIFIED
        self._operation_count += 1

    def _get_sheet(self, name: str) -> Result[SheetData]:
        if self._workbook is None:
            return Err(DocError(code=ErrorCode.OPERATION_FAILED, message="No workbook open"))
        sheet = self._workbook.sheets.get(name)
        if sheet is None:
            return Err(DocError.element_not_found("sheet", name, "workbook"))
        return Ok(sheet)

    @staticmethod
    def _validate_index(row: int, col: int) -> Optional[DocError]:
        if row < 1 or col < 1:
            return DocError.invalid_position((row, col), "row >= 1 and col >= 1")
        return None

    def list_sheets(self) -> Result[List[str]]:
        """List sheet names in workbook order."""
        if self._workbook is None:
            return Err(DocError(code=ErrorCode.OPERATION_FAILED, message="No workbook open"))
        return Ok(list(self._workbook.sheets.keys()))

    def add_sheet(self, name: str) -> Result[str]:
        """Add a new worksheet."""
        if self._workbook is None:
            return Err(DocError(code=ErrorCode.OPERATION_FAILED, message="No workbook open"))

        sheet_name = name.strip()
        if not sheet_name:
            return Err(
                DocError(
                    code=ErrorCode.INVALID_ARGUMENT,
                    message="Sheet name cannot be empty",
                )
            )
        if sheet_name in self._workbook.sheets:
            return Err(
                DocError(
                    code=ErrorCode.VALIDATION_FAILED,
                    message=f"Sheet already exists: {sheet_name}",
                )
            )

        self._workbook.sheets[sheet_name] = SheetData(name=sheet_name)
        self._mark_modified()
        return Ok(sheet_name)

    def rename_sheet(self, old_name: str, new_name: str) -> Result[None]:
        """Rename a worksheet while preserving order."""
        if self._workbook is None:
            return Err(DocError(code=ErrorCode.OPERATION_FAILED, message="No workbook open"))

        if old_name not in self._workbook.sheets:
            return Err(DocError.element_not_found("sheet", old_name, "workbook"))
        new_clean = new_name.strip()
        if not new_clean:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message="New sheet name cannot be empty"))
        if new_clean in self._workbook.sheets and new_clean != old_name:
            return Err(
                DocError(
                    code=ErrorCode.VALIDATION_FAILED,
                    message=f"Sheet already exists: {new_clean}",
                )
            )

        reordered: "OrderedDict[str, SheetData]" = OrderedDict()
        for name, sheet in self._workbook.sheets.items():
            if name == old_name:
                sheet.name = new_clean
                reordered[new_clean] = sheet
            else:
                reordered[name] = sheet

        self._workbook.sheets = reordered
        self._mark_modified()
        return Ok(None)

    def delete_sheet(self, name: str) -> Result[None]:
        """Delete a worksheet."""
        if self._workbook is None:
            return Err(DocError(code=ErrorCode.OPERATION_FAILED, message="No workbook open"))
        if name not in self._workbook.sheets:
            return Err(DocError.element_not_found("sheet", name, "workbook"))
        if len(self._workbook.sheets) == 1:
            return Err(
                DocError(
                    code=ErrorCode.VALIDATION_FAILED,
                    message="Cannot delete the only sheet in workbook",
                )
            )
        del self._workbook.sheets[name]
        self._mark_modified()
        return Ok(None)

    def get_cell(self, sheet: str, row: int, col: int) -> Result[CellRef]:
        """Read a cell value/formula."""
        idx_error = self._validate_index(row, col)
        if idx_error:
            return Err(idx_error)

        sheet_result = self._get_sheet(sheet)
        if sheet_result.is_err():
            return Err(sheet_result.unwrap_err())

        target_sheet = sheet_result.unwrap()
        cell_data = target_sheet.cells.get((row, col), CellValue())
        return Ok(
            CellRef(
                sheet=sheet,
                row=row,
                col=col,
                cell=indices_to_cell_ref(row, col),
                value=cell_data.value,
                formula=cell_data.formula,
            )
        )

    def set_cell(self, sheet: str, row: int, col: int, value: Any) -> Result[CellRef]:
        """Set a raw value into a cell."""
        idx_error = self._validate_index(row, col)
        if idx_error:
            return Err(idx_error)

        sheet_result = self._get_sheet(sheet)
        if sheet_result.is_err():
            return Err(sheet_result.unwrap_err())

        target_sheet = sheet_result.unwrap()
        key = (row, col)
        if value is None:
            target_sheet.cells.pop(key, None)
        else:
            target_sheet.cells[key] = CellValue(value=value, formula=None)
        self._mark_modified()
        return self.get_cell(sheet, row, col)

    def set_formula(self, sheet: str, row: int, col: int, formula: str) -> Result[CellRef]:
        """Set an Excel formula into a cell."""
        idx_error = self._validate_index(row, col)
        if idx_error:
            return Err(idx_error)
        if not formula or not formula.strip():
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message="Formula cannot be empty"))

        sheet_result = self._get_sheet(sheet)
        if sheet_result.is_err():
            return Err(sheet_result.unwrap_err())
        target_sheet = sheet_result.unwrap()

        normalized = formula.strip()
        if normalized.startswith("="):
            normalized = normalized[1:]

        key = (row, col)
        existing_value = target_sheet.cells.get(key, CellValue()).value
        target_sheet.cells[key] = CellValue(value=existing_value, formula=normalized)
        self._mark_modified()
        return self.get_cell(sheet, row, col)

    def append_row(self, sheet: str, values: List[Any], start_col: int = 1) -> Result[int]:
        """Append a row at the first empty row after used range."""
        if start_col < 1:
            return Err(DocError.invalid_position(start_col, "start_col >= 1"))
        sheet_result = self._get_sheet(sheet)
        if sheet_result.is_err():
            return Err(sheet_result.unwrap_err())
        target_sheet = sheet_result.unwrap()
        max_row, _ = target_sheet.dimensions()
        row_index = max_row + 1 if max_row > 0 else 1
        for offset, value in enumerate(values):
            col = start_col + offset
            if value is not None:
                target_sheet.cells[(row_index, col)] = CellValue(value=value)
        self._mark_modified()
        return Ok(row_index)

    def set_range(self, sheet: str, start_row: int, start_col: int, values: List[List[Any]]) -> Result[int]:
        """Set a rectangular range from a 2D list."""
        idx_error = self._validate_index(start_row, start_col)
        if idx_error:
            return Err(idx_error)
        if not values:
            return Ok(0)

        sheet_result = self._get_sheet(sheet)
        if sheet_result.is_err():
            return Err(sheet_result.unwrap_err())
        target_sheet = sheet_result.unwrap()

        written = 0
        for r_offset, row_values in enumerate(values):
            for c_offset, value in enumerate(row_values):
                key = (start_row + r_offset, start_col + c_offset)
                if value is None:
                    target_sheet.cells.pop(key, None)
                else:
                    target_sheet.cells[key] = CellValue(value=value)
                written += 1

        self._mark_modified()
        return Ok(written)

    def get_range(
        self,
        sheet: str,
        start_row: int,
        start_col: int,
        end_row: int,
        end_col: int,
    ) -> Result[List[List[Any]]]:
        """Read a rectangular range into a 2D list."""
        if start_row < 1 or start_col < 1 or end_row < start_row or end_col < start_col:
            return Err(
                DocError(
                    code=ErrorCode.INVALID_RANGE,
                    message=f"Invalid range: ({start_row},{start_col}) to ({end_row},{end_col})",
                )
            )
        sheet_result = self._get_sheet(sheet)
        if sheet_result.is_err():
            return Err(sheet_result.unwrap_err())
        target_sheet = sheet_result.unwrap()

        rows: List[List[Any]] = []
        for row in range(start_row, end_row + 1):
            row_values: List[Any] = []
            for col in range(start_col, end_col + 1):
                cell = target_sheet.cells.get((row, col))
                if cell is None:
                    row_values.append(None)
                elif cell.formula:
                    row_values.append(f"={cell.formula}")
                else:
                    row_values.append(cell.value)
            rows.append(row_values)
        return Ok(rows)

    def clear_range(
        self,
        sheet: str,
        start_row: int,
        start_col: int,
        end_row: int,
        end_col: int,
    ) -> Result[int]:
        """Clear values/formulas in a rectangular range."""
        if start_row < 1 or start_col < 1 or end_row < start_row or end_col < start_col:
            return Err(
                DocError(
                    code=ErrorCode.INVALID_RANGE,
                    message=f"Invalid range: ({start_row},{start_col}) to ({end_row},{end_col})",
                )
            )
        sheet_result = self._get_sheet(sheet)
        if sheet_result.is_err():
            return Err(sheet_result.unwrap_err())
        target_sheet = sheet_result.unwrap()

        cleared = 0
        keys = list(target_sheet.cells.keys())
        for row, col in keys:
            if start_row <= row <= end_row and start_col <= col <= end_col:
                del target_sheet.cells[(row, col)]
                cleared += 1
        if cleared > 0:
            self._mark_modified()
        return Ok(cleared)

    def replace_text(self, sheet: str, old_text: str, new_text: str) -> Result[int]:
        """Find/replace text in string cells of a sheet."""
        if not old_text:
            return Err(DocError(code=ErrorCode.INVALID_ARGUMENT, message="old_text cannot be empty"))

        sheet_result = self._get_sheet(sheet)
        if sheet_result.is_err():
            return Err(sheet_result.unwrap_err())
        target_sheet = sheet_result.unwrap()

        count = 0
        for cell in target_sheet.cells.values():
            if isinstance(cell.value, str) and old_text in cell.value:
                cell.value = cell.value.replace(old_text, new_text)
                count += 1
        if count > 0:
            self._mark_modified()
        return Ok(count)

    def get_stats(self) -> Result[Dict[str, Any]]:
        """Return workbook-level stats for planning and verification."""
        if self._workbook is None:
            return Err(DocError(code=ErrorCode.OPERATION_FAILED, message="No workbook open"))

        per_sheet: Dict[str, Dict[str, int]] = {}
        total_cells = 0
        for name, sheet in self._workbook.sheets.items():
            max_row, max_col = sheet.dimensions()
            cell_count = len(sheet.cells)
            total_cells += cell_count
            per_sheet[name] = {
                "cells": cell_count,
                "max_row": max_row,
                "max_col": max_col,
            }

        return Ok(
            {
                "sheet_count": len(self._workbook.sheets),
                "total_cells": total_cells,
                "operation_count": self._operation_count,
                "sheets": per_sheet,
            }
        )

    @staticmethod
    def _load_shared_strings(zf: zipfile.ZipFile) -> List[str]:
        if "xl/sharedStrings.xml" not in zf.namelist():
            return []
        data = zf.read("xl/sharedStrings.xml")
        root = ET.fromstring(data)
        items = []
        for si in root.findall(_qname(NS_MAIN, "si")):
            # Gather all text nodes for rich text compatibility.
            parts = [t.text or "" for t in si.findall(".//" + _qname(NS_MAIN, "t"))]
            items.append("".join(parts))
        return items

    @classmethod
    def _parse_sheet(cls, xml_data: bytes, shared_strings: List[str]) -> Dict[Tuple[int, int], CellValue]:
        root = ET.fromstring(xml_data)
        cells: Dict[Tuple[int, int], CellValue] = {}
        for c in root.findall(".//" + _qname(NS_MAIN, "c")):
            ref = c.attrib.get("r")
            if not ref:
                continue
            try:
                row, col = cell_ref_to_indices(ref)
            except ValueError:
                continue

            t = c.attrib.get("t")
            f_elem = c.find(_qname(NS_MAIN, "f"))
            v_elem = c.find(_qname(NS_MAIN, "v"))
            inline_elem = c.find(_qname(NS_MAIN, "is"))
            formula = f_elem.text if f_elem is not None and f_elem.text else None
            value: Any = None

            if t == "inlineStr" and inline_elem is not None:
                text_nodes = [n.text or "" for n in inline_elem.findall(".//" + _qname(NS_MAIN, "t"))]
                value = "".join(text_nodes)
            elif t == "s" and v_elem is not None and v_elem.text is not None:
                idx = int(v_elem.text)
                if 0 <= idx < len(shared_strings):
                    value = shared_strings[idx]
            elif t == "b" and v_elem is not None:
                value = v_elem.text == "1"
            elif v_elem is not None and v_elem.text is not None:
                value = _parse_number(v_elem.text)

            if value is not None or formula is not None:
                cells[(row, col)] = CellValue(value=value, formula=formula)

        return cells

    @classmethod
    def _load_xlsx(cls, path: Path) -> Result[WorkbookData]:
        try:
            with zipfile.ZipFile(path, "r") as zf:
                workbook_xml = zf.read("xl/workbook.xml")
                rels_xml = zf.read("xl/_rels/workbook.xml.rels")
                shared_strings = cls._load_shared_strings(zf)

                rels_root = ET.fromstring(rels_xml)
                rel_id_to_target: Dict[str, str] = {}
                for rel in rels_root.findall(_qname(NS_REL, "Relationship")):
                    rid = rel.attrib.get("Id")
                    target = rel.attrib.get("Target")
                    if rid and target:
                        rel_id_to_target[rid] = target

                workbook_root = ET.fromstring(workbook_xml)
                sheets_root = workbook_root.find(_qname(NS_MAIN, "sheets"))
                if sheets_root is None:
                    return Err(
                        DocError(
                            code=ErrorCode.FILE_CORRUPTED,
                            message=f"Workbook has no sheets: {path}",
                            source_file=str(path),
                        )
                    )

                sheets: "OrderedDict[str, SheetData]" = OrderedDict()
                for sheet_elem in sheets_root.findall(_qname(NS_MAIN, "sheet")):
                    name = sheet_elem.attrib.get("name")
                    rid = sheet_elem.attrib.get(_qname(NS_DOC_REL, "id"))
                    if not name or not rid:
                        continue
                    target = rel_id_to_target.get(rid)
                    if not target:
                        continue
                    sheet_path = f"xl/{target.lstrip('/')}"
                    if not sheet_path.startswith("xl/"):
                        sheet_path = f"xl/{target}"
                    if sheet_path not in zf.namelist():
                        continue
                    sheet_xml = zf.read(sheet_path)
                    cells = cls._parse_sheet(sheet_xml, shared_strings)
                    sheets[name] = SheetData(name=name, cells=cells)

                if not sheets:
                    sheets["Sheet1"] = SheetData(name="Sheet1")

                return Ok(WorkbookData(sheets=sheets))
        except Exception as exc:
            return Err(
                DocError(
                    code=ErrorCode.FILE_CORRUPTED,
                    message=f"Failed to parse workbook: {path}",
                    source_file=str(path),
                    cause=exc,
                )
            )

    @staticmethod
    def _serialize_cell(cell_elem: ET.Element, cell: CellValue) -> None:
        if cell.formula:
            f = ET.SubElement(cell_elem, _qname(NS_MAIN, "f"))
            f.text = cell.formula

        value = cell.value
        if value is None:
            return
        if isinstance(value, bool):
            cell_elem.set("t", "b")
            v = ET.SubElement(cell_elem, _qname(NS_MAIN, "v"))
            v.text = "1" if value else "0"
            return
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            v = ET.SubElement(cell_elem, _qname(NS_MAIN, "v"))
            v.text = str(value)
            return

        # Default string representation as inline string.
        cell_elem.set("t", "inlineStr")
        is_elem = ET.SubElement(cell_elem, _qname(NS_MAIN, "is"))
        t_elem = ET.SubElement(is_elem, _qname(NS_MAIN, "t"))
        text = str(value)
        if text and (text[0].isspace() or text[-1].isspace()):
            t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t_elem.text = text

    @classmethod
    def _build_sheet_xml(cls, sheet: SheetData) -> bytes:
        root = ET.Element(_qname(NS_MAIN, "worksheet"))
        sheet_data = ET.SubElement(root, _qname(NS_MAIN, "sheetData"))

        row_map: Dict[int, List[Tuple[int, CellValue]]] = {}
        for (row, col), cell in sorted(sheet.cells.items()):
            row_map.setdefault(row, []).append((col, cell))

        for row, items in sorted(row_map.items()):
            row_elem = ET.SubElement(sheet_data, _qname(NS_MAIN, "row"), {"r": str(row)})
            for col, cell in sorted(items, key=lambda x: x[0]):
                cell_ref = indices_to_cell_ref(row, col)
                c_elem = ET.SubElement(row_elem, _qname(NS_MAIN, "c"), {"r": cell_ref})
                cls._serialize_cell(c_elem, cell)

        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _build_workbook_xml(sheet_names: List[str]) -> bytes:
        root = ET.Element(_qname(NS_MAIN, "workbook"))
        sheets = ET.SubElement(root, _qname(NS_MAIN, "sheets"))
        for idx, name in enumerate(sheet_names, start=1):
            ET.SubElement(
                sheets,
                _qname(NS_MAIN, "sheet"),
                {
                    "name": name,
                    "sheetId": str(idx),
                    _qname(NS_DOC_REL, "id"): f"rId{idx}",
                },
            )
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _build_workbook_rels_xml(sheet_count: int) -> bytes:
        root = ET.Element(_qname(NS_REL, "Relationships"))
        for idx in range(1, sheet_count + 1):
            ET.SubElement(
                root,
                _qname(NS_REL, "Relationship"),
                {
                    "Id": f"rId{idx}",
                    "Type": (
                        "http://schemas.openxmlformats.org/officeDocument/2006/"
                        "relationships/worksheet"
                    ),
                    "Target": f"worksheets/sheet{idx}.xml",
                },
            )
        ET.SubElement(
            root,
            _qname(NS_REL, "Relationship"),
            {
                "Id": f"rId{sheet_count + 1}",
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
                "Target": "styles.xml",
            },
        )
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _build_root_rels_xml() -> bytes:
        root = ET.Element(_qname(NS_REL, "Relationships"))
        ET.SubElement(
            root,
            _qname(NS_REL, "Relationship"),
            {
                "Id": "rId1",
                "Type": (
                    "http://schemas.openxmlformats.org/officeDocument/2006/"
                    "relationships/officeDocument"
                ),
                "Target": "xl/workbook.xml",
            },
        )
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _build_content_types_xml(sheet_count: int) -> bytes:
        root = ET.Element(_qname(NS_CONTENT_TYPES, "Types"))
        ET.SubElement(
            root,
            _qname(NS_CONTENT_TYPES, "Default"),
            {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"},
        )
        ET.SubElement(
            root,
            _qname(NS_CONTENT_TYPES, "Default"),
            {"Extension": "xml", "ContentType": "application/xml"},
        )
        ET.SubElement(
            root,
            _qname(NS_CONTENT_TYPES, "Override"),
            {
                "PartName": "/xl/workbook.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
            },
        )
        for idx in range(1, sheet_count + 1):
            ET.SubElement(
                root,
                _qname(NS_CONTENT_TYPES, "Override"),
                {
                    "PartName": f"/xl/worksheets/sheet{idx}.xml",
                    "ContentType": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.worksheet+xml"
                    ),
                },
            )
        ET.SubElement(
            root,
            _qname(NS_CONTENT_TYPES, "Override"),
            {
                "PartName": "/xl/styles.xml",
                "ContentType": (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.styles+xml"
                ),
            },
        )
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _minimal_styles_xml() -> bytes:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<fonts count=\"1\"><font><sz val=\"11\"/><name val=\"Calibri\"/></font></fonts>"
            "<fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills>"
            "<borders count=\"1\"><border/></borders>"
            "<cellStyleXfs count=\"1\"><xf/></cellStyleXfs>"
            "<cellXfs count=\"1\"><xf xfId=\"0\"/></cellXfs>"
            "<cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles>"
            "</styleSheet>"
        )
        return xml.encode("utf-8")

    @classmethod
    def _write_xlsx(cls, path: Path, workbook: WorkbookData) -> Result[None]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            sheet_names = list(workbook.sheets.keys())
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("[Content_Types].xml", cls._build_content_types_xml(len(sheet_names)))
                zf.writestr("_rels/.rels", cls._build_root_rels_xml())
                zf.writestr("xl/workbook.xml", cls._build_workbook_xml(sheet_names))
                zf.writestr(
                    "xl/_rels/workbook.xml.rels",
                    cls._build_workbook_rels_xml(len(sheet_names)),
                )
                zf.writestr("xl/styles.xml", cls._minimal_styles_xml())
                for idx, sheet_name in enumerate(sheet_names, start=1):
                    sheet = workbook.sheets[sheet_name]
                    zf.writestr(f"xl/worksheets/sheet{idx}.xml", cls._build_sheet_xml(sheet))
            return Ok(None)
        except Exception as exc:
            return Err(
                DocError(
                    code=ErrorCode.OPERATION_FAILED,
                    message=f"Failed to save workbook: {path}",
                    source_file=str(path),
                    cause=exc,
                )
            )
