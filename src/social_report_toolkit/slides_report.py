"""Stage 3: build a short PowerPoint deck from the same summary numbers as the Excel report."""
from __future__ import annotations

from typing import List, Optional

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

from .summary import build_summary

TITLE_SLIDE = 0
BULLETS_SLIDE = 1
TITLE_ONLY_SLIDE = 5
MISSING = "–"


def fmt_int(value: Optional[float]) -> str:
    return MISSING if value is None else f"{value:,.0f}"


def fmt_dec(value: Optional[float]) -> str:
    return MISSING if value is None else f"{value:,.1f}"


def fmt_pct(value: Optional[float]) -> str:
    return MISSING if value is None else f"{value:.2%}"


def add_title_slide(prs: Presentation, title: str, subtitle: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[TITLE_SLIDE])
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle


def add_bullets_slide(prs: Presentation, title: str, bullets: List[str]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[BULLETS_SLIDE])
    slide.shapes.title.text = title
    body = slide.placeholders[1].text_frame
    body.text = bullets[0]
    for bullet in bullets[1:]:
        body.add_paragraph().text = bullet


def headline_bullets(summary: dict) -> List[str]:
    """The 'At a glance' lines. Every average says how many videos it is based on."""
    overall = summary["overall"]
    bullets = [
        f"{overall['videos']} videos, {fmt_int(overall['total_views'])} total views",
        f"Engagement rate {fmt_pct(overall['engagement_rate'])} "
        f"(from {overall['videos_in_engagement_rate']} of {overall['videos']} videos)",
        f"Median views per day {fmt_dec(overall['median_views_per_day'])} "
        f"(from {overall['videos_in_views_per_day']} of {overall['videos']} videos; under 1 day old excluded)",
    ]
    for group in summary["by_format"]:
        label = group["format"].replace("_", "-").capitalize()
        bullets.append(f"{label}: {group['videos']} videos, engagement rate {fmt_pct(group['engagement_rate'])}")
    return bullets

TABLE_COLUMNS = [
    ("videos", "Videos", fmt_int),
    ("total_views", "Total views", fmt_int),
    ("engagement_rate", "Engagement", fmt_pct),
    ("median_views_per_day", "Median views/day", fmt_dec),
    ("videos_in_views_per_day", "Videos in views/day", fmt_int),
]
FONT_SIZE = Pt(12)


def _set_cell(cell, text: str) -> None:
    cell.text = text
    for run in cell.text_frame.paragraphs[0].runs:
        run.font.size = FONT_SIZE


def add_table_slide(prs: Presentation, title: str, label_header: str, label_key: str,
                    rows: List[dict]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[TITLE_ONLY_SLIDE])
    slide.shapes.title.text = title

    n_rows, n_cols = len(rows) + 1, len(TABLE_COLUMNS) + 1
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(0.5), Inches(1.6), Inches(9), Inches(0.4 * n_rows))
    table = shape.table

    headers = [label_header] + [header for _, header, _ in TABLE_COLUMNS]
    for col, header in enumerate(headers):
        _set_cell(table.cell(0, col), header)
    for r, row in enumerate(rows, start=1):
        _set_cell(table.cell(r, 0), str(row[label_key]))
        for col, (key, _, fmt) in enumerate(TABLE_COLUMNS, start=1):
            _set_cell(table.cell(r, col), fmt(row[key]))


def add_chart_slide(prs: Presentation, title: str, labels: List[str], values: List[Optional[float]],
                    number_format: str, horizontal: bool, note: Optional[str] = None) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[TITLE_ONLY_SLIDE])
    slide.shapes.title.text = title

    data = CategoryChartData()
    data.categories = labels
    data.add_series(title, values)

    chart_type = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    chart = slide.shapes.add_chart(chart_type, Inches(0.5), Inches(1.5), Inches(9), Inches(4.8), data).chart
    chart.has_legend = False
    chart.value_axis.tick_labels.number_format = number_format
    chart.value_axis.tick_labels.number_format_is_linked = False
    if horizontal:
        chart.category_axis.reverse_order = True

    if note:
        box = slide.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(9), Inches(0.6))
        box.text_frame.text = note
        box.text_frame.word_wrap = True
        for run in box.text_frame.paragraphs[0].runs:
            run.font.size = FONT_SIZE


def build_deck(dataset: dict) -> Presentation:
    """Build the 5-slide deck from a cleaned dataset."""
    if dataset["source"] != "clean":
        raise ValueError(f"Reports need a cleaned dataset, got '{dataset['source']}'")
    rows = dataset["rows"]
    if not rows:
        raise ValueError("Dataset has no rows")
    summary = build_summary(rows)
    dates = sorted(row["published_at_utc"] for row in rows)

    prs = Presentation()
    add_title_slide(prs, "YouTube performance report",
                    f"Posts from {dates[0][:10]} to {dates[-1][:10]} (UTC)\nData pulled {dataset['pulled_at']}")
    add_bullets_slide(prs, "At a glance", headline_bullets(summary))
    add_table_slide(prs, "By account", "Account", "account_name", summary["by_account"])

    accounts = summary["by_account"]
    add_chart_slide(prs, "Engagement rate by account",
                    [a["account_name"] for a in accounts],
                    [a["engagement_rate"] for a in accounts],
                    "0%", horizontal=True)

    days = summary["by_day"]
    add_chart_slide(prs, "Median views per day by posting day (US Eastern)",
                    [d["posted_day"] for d in days],
                    [d["median_views_per_day"] for d in days],
                    "#,##0", horizontal=False,
                    note="Videos behind each bar: " + ", ".join(
                        f"{d['posted_day']} {d['videos_in_views_per_day']}" for d in days))
    return prs