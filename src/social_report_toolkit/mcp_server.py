"""MCP server: lets an AI agent pull YouTube stats and export them, without handling the numbers itself."""
from __future__ import annotations

import os
from typing import List, Dict

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from .datasets import load_dataset, save_dataset
from .export import export_csv as write_csv
from .youtube import pull_channel
from .clean import clean_dataset as make_clean_dataset
from .report import build_report as make_report
from .summary import build_summary
from .verify import build_facts, check_narrative as run_checks

from .comments import comments_page, export_review_sheet, save_labels, score_review, theme_counts
from .comments import pull_comments as fetch_comments

MAX_CHANNELS = 10

mcp = MCPServer("social-report-toolkit")


def _api_key() -> str:
    load_dotenv()
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is not set")
    return key

MAX_NARRATIVE_CHARS = 20_000
VERDICTS = ["verified", "wrong_subject", "unclear_subject", "not_found"]


def _clean_summary(dataset_id: str):
    dataset = load_dataset(dataset_id)
    if dataset["source"] != "clean":
        raise ValueError(f"Needs a cleaned dataset (from clean_dataset), got '{dataset['source']}'")
    if not dataset["rows"]:
        raise ValueError("Dataset has no rows")
    return dataset, build_summary(dataset["rows"])


@mcp.tool()
def pull_youtube(handles: List[str], limit: int = 50) -> dict:
    """Pull the most recent videos (title, publish date, duration, views, likes, comments)
    for 1-10 YouTube channels and save them as a dataset. Pass channel handles like
    "@fallontonight". limit = videos per channel (1-50, default 50).
    Returns a dataset_id and a summary, not the data itself. Pass the dataset_id to
    clean_dataset for analysis-ready metrics, or to export_csv for the raw CSV. Hidden like counts and disabled comments are stored as
    blank, never as 0."""
    if not 1 <= len(handles) <= MAX_CHANNELS:
        raise ValueError(f"Give between 1 and {MAX_CHANNELS} channel handles")
    limit = max(1, min(limit, 50))
    api_key = _api_key()

    rows = []
    per_channel = {}
    for handle in handles:
        try:
            channel_rows = pull_channel(handle, api_key, limit)
        except Exception as e:
            raise RuntimeError(f"{handle}: {str(e).replace(api_key, '[REDACTED]')}") from None
        per_channel[handle] = len(channel_rows)
        rows += channel_rows

    dataset_id = save_dataset(rows, "youtube")
    return {
        "dataset_id": dataset_id,
        "total_videos": len(rows),
        "videos_per_channel": per_channel,
        "videos_with_hidden_likes": sum(1 for row in rows if row["likes"] is None),
        "videos_with_comments_off": sum(1 for row in rows if row["comments"] is None),
    }

@mcp.tool()
def pull_comments(video: str, limit: int = 200) -> dict:
    """Fetch up to `limit` (1-500) top-level comments on a YouTube video (link or ID) and save
    them as a dataset. Author names are not stored. Comments come in YouTube's relevance order
    (most liked/discussed first), so they are NOT a random sample of all viewers.
    Next: read every page with get_comments_page, then call save_comment_labels."""
    limit = max(1, min(limit, 500))
    api_key = _api_key()
    try:
        dataset_id = fetch_comments(video, api_key, limit)
    except Exception as e:
        raise RuntimeError(str(e).replace(api_key, "[REDACTED]")) from None
    rows = load_dataset(dataset_id)["rows"]
    return {
        "dataset_id": dataset_id,
        "video_title": rows[0]["video_title"],
        "comments": len(rows),
        "replies_not_included": sum(row["replies"] for row in rows),
    }


@mcp.tool()
def get_comments_page(dataset_id: str, offset: int = 0) -> dict:
    """Read up to 50 comments (comment_id, text, likes) from a comments dataset, starting at
    `offset`. Keep calling with next_offset until it is null, so you have read EVERY comment
    before choosing themes."""
    return comments_page(dataset_id, offset)


@mcp.tool()
def save_comment_labels(dataset_id: str, themes: Dict[str, str], labels: Dict[str, str]) -> dict:
    """Save one theme for every comment in a comments dataset.
    themes: 3-9 theme names, each mapped to a one-line definition of what belongs in it
    (names can't contain commas; 'Other' is added automatically for comments that fit nowhere).
    labels: comment_id -> theme name, for EVERY comment.
    Returns the new labelled dataset_id and theme counts calculated in code.
    Next: call create_review_sheet so the user can check a random sample blind.
    Do NOT show the user individual comment labels before they have finished that review."""
    labelled_id = save_labels(dataset_id, themes, labels)
    data = load_dataset(labelled_id)
    return {"dataset_id": labelled_id, "themes": theme_counts(data["rows"], data["meta"]["themes"])}


@mcp.tool()
def create_review_sheet(dataset_id: str) -> dict:
    """Create a BLIND review sheet from a labelled dataset: 30 random comments WITHOUT the AI's
    labels, with a theme dropdown and the theme definitions. Tell the user to label every comment,
    save the file in the same place with the same name, then ask you to score it."""
    path = export_review_sheet(dataset_id)
    return {"review_sheet": str(path.resolve())}


@mcp.tool()
def score_comment_review(dataset_id: str) -> dict:
    """Compare the user's completed blind review with the AI's labels. Returns the agreement
    rate, agreement_95_range (the likely range of the TRUE agreement given the small sample;
    always report it alongside the rate), agreement per AI theme, and every disagreement."""
    return score_review(dataset_id)


@mcp.tool()
def export_csv(dataset_id: str) -> dict:
    """Write a saved dataset (from pull_youtube) to a CSV file that opens in Excel.
    Returns the full path of the CSV and its row count."""
    path = write_csv(dataset_id)
    rows = len(load_dataset(dataset_id)["rows"])
    return {"csv_path": str(path.resolve()), "rows": rows}


@mcp.tool()
def clean_dataset(dataset_id: str) -> dict:
    """Clean a raw YouTube dataset (from pull_youtube) into an analysis-ready dataset and
    return its new dataset_id. Adds: posting day/hour in US Eastern time, format
    (short_form / long_form), engagement_rate = (likes + comments) / views as a fraction,
    age_days at pull time, and views_per_day (blank for videos under 1 day old).
    Metrics are left blank, never 0, when likes or comments are hidden.
    The raw dataset is not changed. Pass the new dataset_id to export_csv."""
    clean_id = make_clean_dataset(dataset_id)
    rows = load_dataset(clean_id)["rows"]
    return {
        "dataset_id": clean_id,
        "derived_from": dataset_id,
        "rows": len(rows),
        "rows_without_engagement_rate": sum(1 for row in rows if row["engagement_rate"] is None),
        "rows_without_views_per_day": sum(1 for row in rows if row["views_per_day"] is None),
        "earliest_post_utc": min((row["published_at_utc"] for row in rows), default=None),
        "latest_post_utc": max((row["published_at_utc"] for row in rows), default=None),
    }
    
@mcp.tool()
def build_report(dataset_id: str) -> dict:
    """Build a client-ready report from a CLEANED dataset (from clean_dataset, not pull_youtube):
    an Excel workbook (Summary tables, Charts, All videos) and a 5-slide PowerPoint deck.
    Every number is calculated in code from the saved data. Each average states how many
    videos it is based on. Returns the full paths of both files."""
    result = make_report(dataset_id)
    return {
        "excel_path": str(result["excel_path"]),
        "slides_path": str(result["slides_path"]),
        "videos": result["videos"],
        "accounts": result["accounts"],
    }
    
@mcp.tool()
def get_report_facts(dataset_id: str) -> dict:
    """Get the summary numbers of a CLEANED dataset, to write a narrative about the report.
    These are the same numbers as build_report's Excel and PowerPoint files.
    Use ONLY these numbers, follow the writing_rules, then call check_narrative with your
    draft and fix every problem it reports before showing the narrative to the user."""
    dataset, summary = _clean_summary(dataset_id)
    dates = sorted(row["published_at_utc"] for row in dataset["rows"])
    return {
        "dataset_id": dataset_id,
        "period_utc": {"from": dates[0][:10], "to": dates[-1][:10]},
        "pulled_at": dataset["pulled_at"],
        "definitions": {
            "engagement_rate": "(likes + comments) / views, as a FRACTION: 0.0342 means 3.42%. "
                               "Weighted across videos with complete counts.",
            "median_views_per_day": "Median of each video's views / age in days. Videos under 1 day old are excluded.",
            "videos_in_engagement_rate": "How many videos the engagement rate is based on.",
            "videos_in_views_per_day": "How many videos the median views per day is based on.",
            "posted_day": "Day of posting in US Eastern time.",
            "format": "short_form = 180 seconds or less (approximation of YouTube Shorts); long_form = longer.",
        },
        "writing_rules": [
            "Use only numbers from this summary. Do not calculate new ones.",
            "One claim per sentence, naming its channel, format or day.",
            "Write rates as percentages (0.0342 -> 3.42% or 3.4%); round, never invent precision.",
            "When a group has few videos (see videos_in_* counts), say so.",
        ],
        "summary": summary,
    }
    
    
@mcp.tool()
def check_narrative(dataset_id: str, narrative: str) -> dict:
    """Check every number in a narrative against a CLEANED dataset's summary.
    Verdicts: verified = correct and attributed to the right channel/format/day;
    wrong_subject = the number exists but belongs to a different subject (see matches_in_data);
    unclear_subject = the number exists but the sentence does not say whose it is;
    not_found = the number is not in the data (invented or wrongly rounded).
    Fix every problem and check again until all_verified is true."""
    if len(narrative) > MAX_NARRATIVE_CHARS:
        raise ValueError(f"Narrative is too long (max {MAX_NARRATIVE_CHARS} characters)")
    _, summary = _clean_summary(dataset_id)
    checks = run_checks(narrative, build_facts(summary))

    problems = [
        {"number": c.number, "verdict": c.verdict, "sentence": c.sentence, "matches_in_data": c.facts}
        for c in checks if c.verdict != "verified"
    ]
    return {
        "numbers_checked": len(checks),
        "all_verified": not problems,
        "counts": {v: sum(1 for c in checks if c.verdict == v) for v in VERDICTS},
        "problems": problems,
    }




def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()