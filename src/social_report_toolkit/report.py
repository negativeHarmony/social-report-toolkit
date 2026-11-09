"""Stage 3: build the Excel and PowerPoint reports for a cleaned dataset in one call."""
from __future__ import annotations

from .datasets import data_dir, load_dataset
from .excel_report import build_workbook
from .slides_report import build_deck


def build_report(dataset_id: str) -> dict:
    """Build and save report_<dataset_id>.xlsx and .pptx. Returns their full paths."""
    dataset = load_dataset(dataset_id)
    workbook, _ = build_workbook(dataset)
    deck = build_deck(dataset)

    out_dir = data_dir().parent / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    excel_path = out_dir / f"report_{dataset_id}.xlsx"
    slides_path = out_dir / f"report_{dataset_id}.pptx"

    workbook.save(excel_path)
    deck.save(slides_path)

    return {
        "excel_path": excel_path.resolve(),
        "slides_path": slides_path.resolve(),
        "videos": len(dataset["rows"]),
        "accounts": len({row["account_name"] for row in dataset["rows"]}),
    }