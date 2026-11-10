import pytest
from openpyxl import load_workbook

from social_report_toolkit.comments import (
    clean_themes, export_review_sheet, review_path, save_labels, score_review,
    theme_counts, video_id_from, wilson_interval,
)
from social_report_toolkit.datasets import load_dataset, save_dataset

THEMES = {"Spam": "Promotes something unrelated to the video", "Praise": "Says something positive"}


@pytest.fixture
def comments_id(tmp_path, monkeypatch):
    monkeypatch.setenv("TOOLKIT_DATA_DIR", str(tmp_path))
    rows = [
        {"video_id": "abcdefghijk", "video_title": "Trailer", "comment_id": f"c{n}",
         "text": f"comment {n}", "likes": n, "replies": 0, "published_at": "2026-11-01T00:00:00Z"}
        for n in range(40)
    ]
    return save_dataset(rows, "comments")


def label_all(comments_id, theme="Praise"):
    ids = [row["comment_id"] for row in load_dataset(comments_id)["rows"]]
    return save_labels(comments_id, THEMES, {i: theme for i in ids})


def fill_review(labelled_id, answer):
    path = review_path(labelled_id)
    wb = load_workbook(path)
    sheet = wb["Review"]
    for row in range(2, sheet.max_row + 1):
        sheet.cell(row=row, column=4, value=answer(row))
    wb.save(path)


# --- Links and themes ---

def test_video_id_from_any_link():
    for link in ["KhTJsfxa-YU",
                 "https://www.youtube.com/watch?v=KhTJsfxa-YU&t=30s",
                 "https://youtu.be/KhTJsfxa-YU",
                 "https://www.youtube.com/shorts/KhTJsfxa-YU",
                 "https://www.youtube.com/watch\\?v=KhTJsfxa-YU"]:
        assert video_id_from(link) == "KhTJsfxa-YU"


def test_other_is_added_automatically():
    assert "Other" in clean_themes(THEMES)


@pytest.mark.parametrize("themes", [
    {"Spam, ads": "has a comma"},
    {"Spam": "one", "spam": "duplicate in a different case"},
    {"Spam": ""},
    {f"Theme {n}": "too many" for n in range(10)},
])
def test_bad_theme_lists_are_refused(themes):
    with pytest.raises(ValueError):
        clean_themes(themes)


# --- Labels ---

def test_every_comment_must_be_labelled(comments_id):
    with pytest.raises(ValueError, match="no label"):
        save_labels(comments_id, THEMES, {"c0": "Praise"})


def test_labels_must_use_listed_themes(comments_id):
    ids = [row["comment_id"] for row in load_dataset(comments_id)["rows"]]
    with pytest.raises(ValueError, match="not in the theme list"):
        save_labels(comments_id, THEMES, {i: "Excitement" for i in ids})


def test_theme_counts_include_unused_themes(comments_id):
    data = load_dataset(label_all(comments_id))
    counts = theme_counts(data["rows"], data["meta"]["themes"])
    assert [(c["theme"], c["comments"]) for c in counts] == [("Praise", 40), ("Spam", 0), ("Other", 0)]


# --- Review sheet ---

def test_review_sheet_is_blind_and_sampled(comments_id):
    path = export_review_sheet(label_all(comments_id), size=30, seed=1)
    sheet = load_workbook(path)["Review"]
    assert [cell.value for cell in sheet[1]] == ["#", "Comment ID", "Comment", "Your theme"]
    assert sheet.max_row == 31
    assert all(sheet.cell(row=r, column=4).value is None for r in range(2, 32))


def test_review_sheet_is_never_overwritten(comments_id):
    labelled_id = label_all(comments_id)
    export_review_sheet(labelled_id)
    with pytest.raises(ValueError, match="already exists"):
        export_review_sheet(labelled_id)


# --- Scoring ---

def test_scoring_counts_agreement(comments_id):
    labelled_id = label_all(comments_id)
    export_review_sheet(labelled_id, seed=1)
    fill_review(labelled_id, lambda row: "Praise" if row <= 25 else "spam")
    result = score_review(labelled_id)
    assert (result["reviewed"], result["agreed"]) == (30, 24)
    assert result["by_ai_theme"] == {"Praise": {"reviewed": 30, "agreed": 24}}


def test_blank_answers_are_refused(comments_id):
    labelled_id = label_all(comments_id)
    export_review_sheet(labelled_id, seed=1)
    fill_review(labelled_id, lambda row: None if row == 5 else "Praise")
    with pytest.raises(ValueError, match="not labelled yet"):
        score_review(labelled_id)


def test_answers_not_on_the_list_are_refused(comments_id):
    labelled_id = label_all(comments_id)
    export_review_sheet(labelled_id, seed=1)
    fill_review(labelled_id, lambda row: "happy" if row == 5 else "Praise")
    with pytest.raises(ValueError, match="happy"):
        score_review(labelled_id)


def test_likely_range():
    low, high = wilson_interval(24, 30)
    assert low == pytest.approx(0.627, abs=0.001)
    assert high == pytest.approx(0.905, abs=0.001)
    low, high = wilson_interval(30, 30)
    assert low == pytest.approx(0.886, abs=0.001)
    assert high == pytest.approx(1.0, abs=0.001)