"""Writes a saved dataset to a CSV file."""
from __future__ import annotations

import csv
from pathlib import Path

from .datasets import data_dir, load_dataset

COLUMNS_BY_SOURCE = {
    "youtube": [
        "pulled_at", "channel_handle", "channel_title", "video_id", "title",
        "published_at", "duration_seconds", "is_short_form", "views", "likes", "comments",
    ],
}

#export to csv with column sources

def export_csv(dataset_id: str) -> Path:
    dataset = load_dataset(dataset_id)
    columns = COLUMNS_BY_SOURCE.get(dataset["source"])
    if columns is None:
        raise ValueError(f"No CSV layout for source {dataset['source']}")

    out = data_dir().parent / "exports" / f"{dataset_id}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in dataset["rows"]:
            writer.writerow({"pulled_at": dataset["pulled_at"], **row})
    return out