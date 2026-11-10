"""Stage 7: comment themes, labelled by AI and checked by a human."""
from __future__ import annotations

import math
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

from .datasets import data_dir, load_dataset, save_dataset
from .youtube import get_comments, get_videos

BARE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
ID_IN_LINK = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})")


def video_id_from(link_or_id: str) -> str:
    """Get the 11-character video ID from a YouTube link or a bare ID."""
    text = link_or_id.strip().replace("\\", "")
    if BARE_ID.fullmatch(text):
        return text
    match = ID_IN_LINK.search(text)
    if not match:
        raise ValueError(f"Could not find a YouTube video ID in: {link_or_id}")
    return match.group(1)


def pull_comments(link_or_id: str, api_key: str, limit: int = 200) -> str:
    """Fetch top-level comments on a video and save them as a 'comments' dataset."""
    video_id = video_id_from(link_or_id)
    videos = get_videos([video_id], api_key)
    if not videos:
        raise ValueError(f"No public video with ID {video_id}")
    title = videos[0]["title"]

    rows = [
        {"video_id": video_id, "video_title": title, **comment}
        for comment in get_comments(video_id, api_key, limit)
    ]
    if not rows:
        raise ValueError(f"'{title}' has no comments")
    return save_dataset(rows, "comments")


OTHER = "Other"
MAX_THEMES = 10
MAX_THEME_LENGTH = 40


OTHER_DEFINITION = "Does not fit any other theme."
MAX_DEFINITION_LENGTH = 200


def clean_themes(themes: Dict[str, str]) -> Dict[str, str]:
    """Tidy themes (name -> definition): no blanks, no duplicates, no commas, always an 'Other'."""
    cleaned: Dict[str, str] = {}
    for theme, definition in themes.items():
        name = theme.strip()
        meaning = (definition or "").strip()
        if not name or len(name) > MAX_THEME_LENGTH:
            raise ValueError(f"Theme names must be 1-{MAX_THEME_LENGTH} characters, got: '{theme}'")
        if "," in name:
            raise ValueError(f"Theme names can't contain commas: '{name}'")
        if name.lower() in [t.lower() for t in cleaned]:
            raise ValueError(f"Duplicate theme: '{name}'")
        if not meaning or len(meaning) > MAX_DEFINITION_LENGTH:
            raise ValueError(f"Theme '{name}' needs a definition of 1-{MAX_DEFINITION_LENGTH} characters")
        cleaned[name] = meaning
    if OTHER.lower() not in [t.lower() for t in cleaned]:
        cleaned[OTHER] = OTHER_DEFINITION
    if len(cleaned) > MAX_THEMES:
        raise ValueError(f"Use at most {MAX_THEMES} themes, including '{OTHER}'")
    return cleaned


def save_labels(dataset_id: str, themes: Dict[str, str], labels: Dict[str, str]) -> str:
    """Validate one theme per comment and save them as a new 'labelled' dataset."""
    dataset = load_dataset(dataset_id)
    if dataset["source"] != "comments":
        raise ValueError(f"Needs a comments dataset, got '{dataset['source']}'")

    themes = clean_themes(themes)
    canonical = {t.lower(): t for t in themes}
    comment_ids = {row["comment_id"] for row in dataset["rows"]}

    missing = comment_ids - labels.keys()
    if missing:
        raise ValueError(f"{len(missing)} comments have no label, e.g. {sorted(missing)[:3]}")
    unknown = labels.keys() - comment_ids
    if unknown:
        raise ValueError(f"{len(unknown)} labels are for comments not in this dataset, e.g. {sorted(unknown)[:3]}")
    invalid = sorted({theme for theme in labels.values() if theme.strip().lower() not in canonical})
    if invalid:
        raise ValueError(f"These labels are not in the theme list: {invalid[:5]}")

    rows = [
        {**row, "theme": canonical[labels[row["comment_id"]].strip().lower()]}
        for row in dataset["rows"]
    ]
    return save_dataset(rows, "labelled", derived_from=dataset_id, pulled_at=dataset["pulled_at"],
                        meta={"themes": list(themes), "definitions": themes})
    
    
REVIEW_SIZE = 30


def review_path(dataset_id: str) -> Path:
    return data_dir().parent / "reviews" / f"review_{dataset_id}.xlsx"


def export_review_sheet(dataset_id: str, size: int = REVIEW_SIZE, seed: Optional[int] = None) -> Path:
    """A blind review sheet: a random sample of comments for a person to label, without the AI's labels."""
    dataset = load_dataset(dataset_id)
    if dataset["source"] != "labelled":
        raise ValueError(f"Needs a labelled dataset (from save_labels), got '{dataset['source']}'")
    path = review_path(dataset_id)
    if path.exists():
        raise ValueError(f"A review sheet already exists: {path}. Fill it in, or delete it to make a new one.")

    themes = dataset["meta"]["themes"]
    definitions = dataset["meta"].get("definitions", {})
    rows = dataset["rows"]
    seed = seed if seed is not None else random.randrange(1_000_000)
    sample = random.Random(seed).sample(rows, min(size, len(rows)))

    wb = Workbook()
    info = wb.active
    info.title = "Instructions"
    for line in [
        "Label each comment on the Review tab YOURSELF, choosing a theme from the dropdown.",
        "The AI's labels are deliberately not in this file, so they can't influence you.",
        "If no theme fits, choose 'Other'. Save the file when done, then run score_review.",
        "",
        f"Dataset: {dataset_id}",
        f"Sample: {len(sample)} of {len(rows)} comments, random seed {seed}",
        "Themes:",
        *[f"  {theme}: {definitions.get(theme, '')}" for theme in themes],
    ]:
        info.append([line])
    info.column_dimensions["A"].width = 100

    review = wb.create_sheet("Review")
    review.append(["#", "Comment ID", "Comment", "Your theme"])
    for cell in review[1]:
        cell.font = Font(bold=True)
    for number, row in enumerate(sample, start=1):
        review.append([number, row["comment_id"], row["text"], None])
    for cell in review["C"][1:]:
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for letter, width in {"A": 5, "B": 30, "C": 80, "D": 25}.items():
        review.column_dimensions[letter].width = width
    review.freeze_panes = "A2"

    lists = wb.create_sheet("Themes")
    for theme in themes:
        lists.append([theme, definitions.get(theme, "")])
        
    options = ",".join(themes)
    if len(options) <= 250:
        source = f'"{options}"'
    else:
        source = f"=Themes!$A$1:$A${len(themes)}"
    dropdown = DataValidation(
        type="list", formula1=source, allow_blank=True,
        showErrorMessage=True, errorTitle="Not a theme", error="Pick one of the themes from the list.",
    )
    review.add_data_validation(dropdown)
    dropdown.add(f"D2:D{len(sample) + 1}")

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path

Z_95 = 1.96


def wilson_interval(agreed: int, total: int) -> Tuple[float, float]:
    """A 95% range for the true agreement rate, given a sample of `total` with `agreed` matches."""
    p = agreed / total
    denominator = 1 + Z_95 ** 2 / total
    centre = (p + Z_95 ** 2 / (2 * total)) / denominator
    margin = Z_95 * math.sqrt(p * (1 - p) / total + Z_95 ** 2 / (4 * total ** 2)) / denominator
    return round(centre - margin, 4), round(centre + margin, 4)


def read_review(path: Path) -> Dict[str, str]:
    """The reviewer's answers: comment ID -> theme. Refuses if any row is still blank."""
    sheet = load_workbook(path, data_only=True)["Review"]
    answers = {}
    blank_rows = []
    rows = sheet.iter_rows(min_row=2, max_col=4, values_only=True)
    for row_number, (_, comment_id, _, theme) in enumerate(rows, start=2):
        if comment_id is None:
            continue
        if theme is None or not str(theme).strip():
            blank_rows.append(row_number)
            continue
        answers[str(comment_id)] = str(theme).strip()
    if blank_rows:
        raise ValueError(f"{len(blank_rows)} comments are not labelled yet (sheet rows {blank_rows[:10]})")
    return answers


def score_review(dataset_id: str) -> dict:
    """Compare the reviewer's themes with the AI's labels: agreement rate, range, per theme, disagreements."""
    dataset = load_dataset(dataset_id)
    if dataset["source"] != "labelled":
        raise ValueError(f"Needs a labelled dataset, got '{dataset['source']}'")
    path = review_path(dataset_id)
    if not path.exists():
        raise ValueError(f"No review sheet at {path}. Create one with export_review_sheet first.")

    answers = read_review(path)
    if not answers:
        raise ValueError("The review sheet has no comments")
    canonical = {t.lower(): t for t in dataset["meta"]["themes"]}
    invalid = sorted({theme for theme in answers.values() if theme.lower() not in canonical})
    if invalid:
        raise ValueError(f"These answers are not themes on the list: {invalid}")
    ai_rows = {row["comment_id"]: row for row in dataset["rows"]}
    unknown = answers.keys() - ai_rows.keys()
    if unknown:
        raise ValueError(f"{len(unknown)} comment IDs in the sheet are not in this dataset")

    agreed = 0
    by_theme = {}
    disagreements = []
    for comment_id, answer in answers.items():
        human = canonical[answer.lower()]
        row = ai_rows[comment_id]
        stats = by_theme.setdefault(row["theme"], {"reviewed": 0, "agreed": 0})
        stats["reviewed"] += 1
        if human == row["theme"]:
            agreed += 1
            stats["agreed"] += 1
        else:
            disagreements.append({"comment": row["text"], "ai_theme": row["theme"], "human_theme": human})

    total = len(answers)
    return {
        "reviewed": total,
        "agreed": agreed,
        "agreement_rate": round(agreed / total, 4),
        "agreement_95_range": wilson_interval(agreed, total),
        "by_ai_theme": by_theme,
        "disagreements": disagreements,
    }
    
MAX_PAGE = 50
MAX_COMMENT_CHARS = 1000


def comments_page(dataset_id: str, offset: int = 0, limit: int = MAX_PAGE) -> dict:
    """A page of comments for the AI to read and label: IDs, text and likes."""
    dataset = load_dataset(dataset_id)
    if dataset["source"] != "comments":
        raise ValueError(f"Needs a comments dataset, got '{dataset['source']}'")
    rows = dataset["rows"]
    offset = max(0, offset)
    limit = max(1, min(limit, MAX_PAGE))
    page = rows[offset:offset + limit]
    next_offset = offset + len(page)
    return {
        "total": len(rows),
        "offset": offset,
        "next_offset": next_offset if next_offset < len(rows) else None,
        "comments": [
            {"comment_id": row["comment_id"], "text": row["text"][:MAX_COMMENT_CHARS], "likes": row["likes"]}
            for row in page
        ],
    }


def theme_counts(rows: List[dict], themes: List[str]) -> List[dict]:
    """How many comments (and likes) each theme has, biggest first. Includes themes with 0 comments."""
    total = len(rows)
    counts = []
    for theme in themes:
        group = [row for row in rows if row["theme"] == theme]
        counts.append({
            "theme": theme,
            "comments": len(group),
            "share": round(len(group) / total, 4) if total else None,
            "likes": sum(row["likes"] for row in group),
        })
    return sorted(counts, key=lambda c: c["comments"], reverse=True)
    
    

