"""Saves pulled data to disk under an ID, so tools can pass the ID around instead of the data."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


# Dataset ID pattern
DATASET_ID_PATTERN = re.compile(r"[a-z]+_\d{8}T\d{6}Z")


# Folder where datasets are stored (read each time, so a .env loaded later still counts)
def data_dir() -> Path:                                                     # ← changed
    return Path(os.getenv("TOOLKIT_DATA_DIR", "data")).expanduser() / "raw"  # ← changed


# Save dataset to disk and return its ID
# Save dataset to disk and return its ID
def save_dataset(rows: List[dict], source: str, derived_from: Optional[str] = None,
                 pulled_at: Optional[str] = None, meta: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    dataset_id = f"{source}_{now:%Y%m%dT%H%M%SZ}"
    data_dir().mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_id": dataset_id,
        "source": source,
        "created_at": now.isoformat(timespec="seconds"),
        "pulled_at": pulled_at or now.isoformat(timespec="seconds"),
        "derived_from": derived_from,
        "meta": meta or {},
        "rows": rows,
    }
    with open(data_dir() / f"{dataset_id}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return dataset_id


# Load a saved dataset by its ID
def load_dataset(dataset_id: str) -> dict:
    if not DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise ValueError(f"Invalid dataset ID: {dataset_id}")
    path = data_dir() / f"{dataset_id}.json"                                # ← changed
    if not path.exists():
        raise ValueError(f"No dataset with ID {dataset_id}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)