"""Stage 3: write the summary and all videos to a formatted Excel workbook."""
from __future__ import annotations

from typing import List, Tuple

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference

from .export import COLUMNS_BY_SOURCE
from .summary import build_summary


TITLE_FONT = Font(bold=True, size=14)
HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="1F3864")

INT = "#,##0"
DEC = "#,##0.0"
PCT = "0.00%"

SUMMARY_COLUMNS = [
    ("videos", "Videos", INT),
    ("total_views", "Total views", INT),
    ("median_views_per_day", "Median views/day", DEC),
    ("videos_in_views_per_day", "Videos in views/day", INT),
    ("engagement_rate", "Engagement rate", PCT),
    ("videos_in_engagement_rate", "Videos in engagement rate", INT),
]


def write_table(ws, start_row: int, title: str, label_key: str, label_header: str,
                rows: List[dict]) -> Tuple[int, int]:
    """Write a titled summary table starting at start_row. Returns (header_row, last_row)."""
    ws.cell(row=start_row, column=1, value=title).font = TITLE_FONT

    header_row = start_row + 1
    headers = [label_header] + [header for _, header, _ in SUMMARY_COLUMNS]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL

    for offset, row in enumerate(rows, start=1):
        excel_row = header_row + offset
        ws.cell(row=excel_row, column=1, value=row[label_key])
        for col, (key, _, number_format) in enumerate(SUMMARY_COLUMNS, start=2):
            cell = ws.cell(row=excel_row, column=col, value=row[key])
            cell.number_format = number_format

    return header_row, header_row + len(rows)

VIDEO_FORMATS = {
    "views": INT, "likes": INT, "comments": INT,
    "engagement_rate": PCT, "views_per_day": DEC, "age_days": "0.00",
}

def _column_of(key: str) -> int:
    """Which Excel column a summary value sits in (column 1 is the label)."""
    keys = [k for k, _, _ in SUMMARY_COLUMNS]
    return keys.index(key) + 2


def bar_chart(ws, table_position: Tuple[int, int], key: str, title: str,
              axis_format: str, horizontal: bool) -> BarChart:
    """A bar chart of one summary column, reading its values from the table on the Summary sheet."""
    header_row, last_row = table_position
    first_data_row = header_row + 1
    col = _column_of(key)

    chart = BarChart()
    chart.type = "bar" if horizontal else "col"
    chart.title = title
    chart.legend = None
    chart.width, chart.height = 20, 10

    chart.add_data(Reference(ws, min_col=col, min_row=first_data_row, max_row=last_row))
    chart.set_categories(Reference(ws, min_col=1, min_row=first_data_row, max_row=last_row))

    chart.y_axis.number_format = axis_format
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    if horizontal:
        chart.x_axis.scaling.orientation = "maxMin"
    return chart


def build_workbook(dataset: dict) -> Tuple[Workbook, dict]:
    """Build the report workbook from a cleaned dataset. Returns the workbook and table positions."""
    if dataset["source"] != "clean":
        raise ValueError(f"Reports need a cleaned dataset, got '{dataset['source']}'")
    rows = dataset["rows"]
    if not rows:
        raise ValueError("Dataset has no rows")
    summary = build_summary(rows)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"

    dates = sorted(row["published_at_utc"] for row in rows)
    ws["A1"] = "YouTube performance report"
    ws["A1"].font = Font(bold=True, size=18)
    ws["A2"] = f"Posts from {dates[0][:10]} to {dates[-1][:10]} (UTC). Data pulled {dataset['pulled_at']}."
    ws["A3"] = f"Source: dataset {dataset['dataset_id']}, derived from {dataset.get('derived_from')}."

    tables = [
        ("overall", "Overall", "label", "", [{"label": "All videos", **summary["overall"]}]),
        ("by_account", "By account", "account_name", "Account", summary["by_account"]),
        ("by_format", "By format", "format", "Format", summary["by_format"]),
        ("by_day", "By posting day (US Eastern)", "posted_day", "Day", summary["by_day"]),
    ]
    positions = {}
    next_row = 5
    for name, title, label_key, label_header, table_rows in tables:
        header_row, last_row = write_table(ws, next_row, title, label_key, label_header, table_rows)
        positions[name] = (header_row, last_row)
        next_row = last_row + 3

    ws.column_dimensions["A"].width = 42
    for col in range(2, len(SUMMARY_COLUMNS) + 2):
        ws.column_dimensions[get_column_letter(col)].width = 18

    videos = wb.create_sheet("All videos")
    columns = COLUMNS_BY_SOURCE["clean"]
    videos.append(columns)
    for cell in videos[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
    for row in rows:
        videos.append([dataset["pulled_at"] if col == "pulled_at" else row[col] for col in columns])

    for col, name in enumerate(columns, start=1):
        letter = get_column_letter(col)
        videos.column_dimensions[letter].width = 45 if name == "title" else 16
        if name in VIDEO_FORMATS:
            for cell in videos[letter][1:]:
                cell.number_format = VIDEO_FORMATS[name]
    videos.freeze_panes = "A2"
    videos.auto_filter.ref = videos.dimensions

    charts = wb.create_sheet("Charts", 1)
    charts.add_chart(bar_chart(ws, positions["by_account"], "engagement_rate",
                               "Engagement rate by account", "0%", horizontal=True), "A1")
    charts.add_chart(bar_chart(ws, positions["by_day"], "median_views_per_day",
                               "Median views per day by posting day (US Eastern)", "#,##0",
                               horizontal=False), "A22")
    return wb, positions