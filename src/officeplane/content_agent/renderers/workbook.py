"""Typed Workbook tree for Excel generation.

Section types: title, subtitle, text, blank, table, chart, kpi.
Cell formats: text, number, integer, currency_usd, currency_eur, percent, date, datetime.
Chart types: bar, column, line, pie, scatter.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Union

log = logging.getLogger("officeplane.renderers.workbook")

SectionType = Literal["title", "subtitle", "text", "blank", "table", "chart", "kpi"]
ChartType = Literal["bar", "column", "line", "pie", "scatter"]
ColumnFormat = Literal[
    "text", "number", "integer", "currency_usd", "currency_eur", "percent", "date", "datetime",
]


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class WorkbookMeta:
    title: str = "Untitled"
    author: str | None = None
    description: str | None = None
    render_hints: dict[str, Any] = field(default_factory=dict)


@dataclass
class Attribution:
    node_id: str
    document_id: str | None = None
    document_title: str | None = None
    section_id: str | None = None
    page_numbers: list[int] = field(default_factory=list)


@dataclass
class TitleSection:
    id: str
    text: str
    span_columns: int = 8
    type: Literal["title"] = "title"


@dataclass
class SubtitleSection:
    id: str
    text: str
    type: Literal["subtitle"] = "subtitle"


@dataclass
class TextSection:
    id: str
    text: str
    type: Literal["text"] = "text"


@dataclass
class BlankSection:
    id: str
    type: Literal["blank"] = "blank"


@dataclass
class TableSection:
    id: str
    name: str
    headers: list[str]
    rows: list[list[Any]]
    column_formats: list[ColumnFormat] = field(default_factory=list)
    totals_row: list[Any] | None = None
    autofilter: bool = True
    style: str = "TableStyleMedium2"
    type: Literal["table"] = "table"


@dataclass
class ChartSection:
    id: str
    chart_type: ChartType
    title: str
    data_ref: str
    categories_col: str
    values_col: str
    width_cells: int = 8
    height_cells: int = 15
    type: Literal["chart"] = "chart"


@dataclass
class KpiSection:
    id: str
    label: str
    value: Any
    format: ColumnFormat = "number"
    type: Literal["kpi"] = "kpi"


Section = Union[TitleSection, SubtitleSection, TextSection, BlankSection,
                TableSection, ChartSection, KpiSection]


@dataclass
class Sheet:
    id: str
    name: str
    sections: list[Section] = field(default_factory=list)
    column_widths: dict[str, float] = field(default_factory=dict)
    freeze_header: bool = True


@dataclass
class Workbook:
    meta: WorkbookMeta = field(default_factory=WorkbookMeta)
    sheets: list[Sheet] = field(default_factory=list)
    attributions: list[Attribution] = field(default_factory=list)
    schema_version: str = "1.0"


def parse_workbook(data: dict[str, Any]) -> Workbook:
    meta_d = data.get("meta") or {}
    wb = Workbook(
        meta=WorkbookMeta(
            title=str(meta_d.get("title") or "Untitled"),
            author=meta_d.get("author"),
            description=meta_d.get("description"),
            render_hints=dict(meta_d.get("render_hints") or {}),
        ),
        schema_version=str(data.get("schema_version") or "1.0"),
    )
    for sh_d in (data.get("sheets") or []):
        if not isinstance(sh_d, dict):
            continue
        sheet = Sheet(
            id=str(sh_d.get("id") or _short_id()),
            name=str(sh_d.get("name") or "Sheet1")[:31],
            column_widths=dict(sh_d.get("column_widths") or {}),
            freeze_header=bool(sh_d.get("freeze_header", True)),
        )
        for sec_d in (sh_d.get("sections") or []):
            if not isinstance(sec_d, dict):
                continue
            t = sec_d.get("type")
            sid = str(sec_d.get("id") or _short_id())
            try:
                if t == "title":
                    sheet.sections.append(TitleSection(
                        id=sid, text=str(sec_d.get("text") or ""),
                        span_columns=int(sec_d.get("span_columns") or 8)))
                elif t == "subtitle":
                    sheet.sections.append(SubtitleSection(id=sid, text=str(sec_d.get("text") or "")))
                elif t == "text":
                    sheet.sections.append(TextSection(id=sid, text=str(sec_d.get("text") or "")))
                elif t == "blank":
                    sheet.sections.append(BlankSection(id=sid))
                elif t == "table":
                    headers = [str(h) for h in (sec_d.get("headers") or [])]
                    rows = [list(r) for r in (sec_d.get("rows") or []) if isinstance(r, list)]
                    sheet.sections.append(TableSection(
                        id=sid, name=str(sec_d.get("name") or f"Table_{sid}"),
                        headers=headers, rows=rows,
                        column_formats=list(sec_d.get("column_formats") or []),
                        totals_row=(list(sec_d["totals_row"]) if isinstance(sec_d.get("totals_row"), list) else None),
                        autofilter=bool(sec_d.get("autofilter", True)),
                        style=str(sec_d.get("style") or "TableStyleMedium2")))
                elif t == "chart":
                    sheet.sections.append(ChartSection(
                        id=sid,
                        chart_type=str(sec_d.get("chart_type") or "bar"),
                        title=str(sec_d.get("title") or ""),
                        data_ref=str(sec_d.get("data_ref") or ""),
                        categories_col=str(sec_d.get("categories_col") or ""),
                        values_col=str(sec_d.get("values_col") or ""),
                        width_cells=int(sec_d.get("width_cells") or 8),
                        height_cells=int(sec_d.get("height_cells") or 15)))
                elif t == "kpi":
                    sheet.sections.append(KpiSection(
                        id=sid, label=str(sec_d.get("label") or ""),
                        value=sec_d.get("value"),
                        format=str(sec_d.get("format") or "number")))
                else:
                    log.warning("unknown section type: %s", t)
            except Exception as e:
                log.warning("failed to parse section %s: %s", sid, e)
        wb.sheets.append(sheet)

    for a in (data.get("attributions") or []):
        if not isinstance(a, dict):
            continue
        wb.attributions.append(Attribution(
            node_id=str(a.get("node_id") or ""),
            document_id=a.get("document_id"),
            document_title=a.get("document_title"),
            section_id=a.get("section_id"),
            page_numbers=list(a.get("page_numbers") or [])))
    return wb


def workbook_to_dict(wb: Workbook) -> dict[str, Any]:
    def _sec(s: Any) -> dict[str, Any]:
        base = {"id": s.id, "type": s.type}
        if isinstance(s, TitleSection):
            base.update(text=s.text, span_columns=s.span_columns)
        elif isinstance(s, (SubtitleSection, TextSection)):
            base.update(text=s.text)
        elif isinstance(s, TableSection):
            base.update(name=s.name, headers=list(s.headers), rows=[list(r) for r in s.rows],
                        column_formats=list(s.column_formats),
                        totals_row=(list(s.totals_row) if s.totals_row else None),
                        autofilter=s.autofilter, style=s.style)
        elif isinstance(s, ChartSection):
            base.update(chart_type=s.chart_type, title=s.title, data_ref=s.data_ref,
                        categories_col=s.categories_col, values_col=s.values_col,
                        width_cells=s.width_cells, height_cells=s.height_cells)
        elif isinstance(s, KpiSection):
            base.update(label=s.label, value=s.value, format=s.format)
        return base

    return {
        "type": "workbook", "schema_version": wb.schema_version,
        "meta": {"title": wb.meta.title, "author": wb.meta.author,
                 "description": wb.meta.description, "render_hints": dict(wb.meta.render_hints)},
        "sheets": [{"id": sh.id, "name": sh.name, "column_widths": dict(sh.column_widths),
                    "freeze_header": sh.freeze_header,
                    "sections": [_sec(s) for s in sh.sections]} for sh in wb.sheets],
        "attributions": [{"node_id": a.node_id, "document_id": a.document_id,
                          "document_title": a.document_title, "section_id": a.section_id,
                          "page_numbers": list(a.page_numbers)} for a in wb.attributions],
    }
