"""Tests for the Workbook typed tree (parse_workbook / workbook_to_dict)."""
import json

from officeplane.content_agent.renderers.workbook import (
    BlankSection,
    ChartSection,
    KpiSection,
    Sheet,
    SubtitleSection,
    TableSection,
    TextSection,
    TitleSection,
    Workbook,
    WorkbookMeta,
    parse_workbook,
    workbook_to_dict,
)


def test_parse_minimal_workbook():
    data = {
        "type": "workbook",
        "schema_version": "1.0",
        "meta": {"title": "My Report"},
        "sheets": [
            {
                "id": "s1",
                "name": "Summary",
                "sections": [],
            }
        ],
        "attributions": [],
    }
    wb = parse_workbook(data)
    assert isinstance(wb, Workbook)
    assert wb.meta.title == "My Report"
    assert wb.schema_version == "1.0"
    assert len(wb.sheets) == 1
    assert wb.sheets[0].name == "Summary"
    assert wb.sheets[0].id == "s1"
    assert wb.sheets[0].sections == []
    assert wb.attributions == []


def test_all_section_types_parsed():
    data = {
        "sheets": [
            {
                "id": "sh1",
                "name": "All Types",
                "sections": [
                    {"type": "title", "id": "t1", "text": "Title Here", "span_columns": 6},
                    {"type": "subtitle", "id": "st1", "text": "Subtitle"},
                    {"type": "text", "id": "tx1", "text": "Some prose"},
                    {"type": "blank", "id": "b1"},
                    {
                        "type": "table",
                        "id": "tbl1",
                        "name": "DataTable",
                        "headers": ["Name", "Value"],
                        "rows": [["Alpha", 100], ["Beta", 200]],
                        "column_formats": ["text", "number"],
                        "totals_row": ["Total", 300],
                        "autofilter": True,
                        "style": "TableStyleMedium2",
                    },
                    {
                        "type": "chart",
                        "id": "ch1",
                        "chart_type": "bar",
                        "title": "Value Chart",
                        "data_ref": "tbl1",
                        "categories_col": "Name",
                        "values_col": "Value",
                        "width_cells": 8,
                        "height_cells": 15,
                    },
                    {
                        "type": "kpi",
                        "id": "k1",
                        "label": "Total Revenue",
                        "value": 999999,
                        "format": "currency_usd",
                    },
                ],
            }
        ]
    }
    wb = parse_workbook(data)
    secs = wb.sheets[0].sections
    assert len(secs) == 7
    assert isinstance(secs[0], TitleSection)
    assert secs[0].text == "Title Here"
    assert secs[0].span_columns == 6

    assert isinstance(secs[1], SubtitleSection)
    assert secs[1].text == "Subtitle"

    assert isinstance(secs[2], TextSection)
    assert secs[2].text == "Some prose"

    assert isinstance(secs[3], BlankSection)

    assert isinstance(secs[4], TableSection)
    assert secs[4].name == "DataTable"
    assert secs[4].headers == ["Name", "Value"]
    assert secs[4].rows == [["Alpha", 100], ["Beta", 200]]
    assert secs[4].column_formats == ["text", "number"]
    assert secs[4].totals_row == ["Total", 300]

    assert isinstance(secs[5], ChartSection)
    assert secs[5].chart_type == "bar"
    assert secs[5].data_ref == "tbl1"

    assert isinstance(secs[6], KpiSection)
    assert secs[6].label == "Total Revenue"
    assert secs[6].value == 999999
    assert secs[6].format == "currency_usd"


def test_sheet_name_truncated_to_31_chars():
    long_name = "A" * 50
    data = {
        "sheets": [
            {"id": "x", "name": long_name, "sections": []}
        ]
    }
    wb = parse_workbook(data)
    assert len(wb.sheets[0].name) == 31
    assert wb.sheets[0].name == "A" * 31


def test_workbook_to_dict_round_trip():
    original = {
        "type": "workbook",
        "schema_version": "1.0",
        "meta": {
            "title": "Round Trip",
            "author": "Tester",
            "description": "A test workbook",
            "render_hints": {"freeze": True},
        },
        "sheets": [
            {
                "id": "sh1",
                "name": "Data",
                "freeze_header": True,
                "column_widths": {"A": 20.0},
                "sections": [
                    {"type": "title", "id": "t1", "text": "Hello", "span_columns": 4},
                    {
                        "type": "table",
                        "id": "tbl1",
                        "name": "SalesTable",
                        "headers": ["Month", "Revenue"],
                        "rows": [["Jan", 5000], ["Feb", 6000]],
                        "column_formats": ["text", "currency_usd"],
                        "totals_row": None,
                        "autofilter": True,
                        "style": "TableStyleMedium2",
                    },
                    {
                        "type": "kpi",
                        "id": "k1",
                        "label": "Total",
                        "value": 11000,
                        "format": "currency_usd",
                    },
                ],
            }
        ],
        "attributions": [
            {
                "node_id": "tbl1",
                "document_id": "doc-abc",
                "document_title": "Sales Report",
                "section_id": None,
                "page_numbers": [1, 2],
            }
        ],
    }

    wb1 = parse_workbook(original)
    d1 = workbook_to_dict(wb1)

    wb2 = parse_workbook(d1)
    d2 = workbook_to_dict(wb2)

    # Serialised form must be stable across two parse→dict cycles
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)

    # Spot-check key values are preserved
    assert d2["meta"]["title"] == "Round Trip"
    assert d2["meta"]["author"] == "Tester"
    assert d2["sheets"][0]["name"] == "Data"
    assert d2["sheets"][0]["sections"][1]["name"] == "SalesTable"
    assert d2["attributions"][0]["document_id"] == "doc-abc"
    assert d2["attributions"][0]["page_numbers"] == [1, 2]
