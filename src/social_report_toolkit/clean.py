"""Stage 2: clean and normalise pulled data into one consistent, analysis-ready schema."""
from __future__ import annotations

from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from .datasets import load_dataset, save_dataset


def engagement_rate(likes: Optional[int], comments: Optional[int], views: Optional[int]) -> Optional[float]:
    """(likes + comments) / views, or None when any part is unknown or views is 0."""
    if likes is None or comments is None or not views:
        return None
    return round((likes + comments) / views, 4)

#youtube gives utc time for posted. convert utc to utc -5 new york time then get the day of the week and hour inutc -5
AUDIENCE_TZ = ZoneInfo("America/New_York") # change Audience tz to convert to preferred timezone


def parse_utc(timestamp: str) -> datetime:
    """Turn YouTube's '2026-11-06T04:00:00Z' into a timezone-aware datetime."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def posting_time(published_at: str) -> dict:
    """When a video went live on the audience's clock: local time, weekday and hour."""
    local = parse_utc(published_at).astimezone(AUDIENCE_TZ)
    return {
        "posted_local": local.isoformat(timespec="minutes"),
        "posted_day": local.strftime("%A"),
        "posted_hour": local.hour,
    }
    
MIN_AGE_DAYS = 1


def views_per_day(views: Optional[int], age_days: float) -> Optional[float]:
    """Average daily views since posting, or None if views are unknown or the video is under a day old."""
    if views is None or age_days < MIN_AGE_DAYS:
        return None
    return round(views / age_days, 1)


def clean_row(row: dict, pulled_at: str) -> dict:
    """Turn one raw Stage 1 row into one cleaned, platform-neutral row."""
    age_days = (parse_utc(pulled_at) - parse_utc(row["published_at"])).total_seconds() / 86400
    return {
        "platform": "youtube",
        "account_handle": row["channel_handle"],
        "account_name": row["channel_title"],
        "post_id": row["video_id"],
        "title": row["title"],
        "published_at_utc": row["published_at"],
        **posting_time(row["published_at"]),
        "format": "short_form" if row["is_short_form"] else "long_form",
        "duration_seconds": row["duration_seconds"],
        "views": row["views"],
        "likes": row["likes"],
        "comments": row["comments"],
        "engagement_rate": engagement_rate(row["likes"], row["comments"], row["views"]),
        "age_days": round(age_days, 2),
        "views_per_day": views_per_day(row["views"], age_days),
    }
    
def clean_dataset(dataset_id: str) -> str:
    """Clean every row of a raw YouTube dataset and save the result as a new 'clean' dataset."""
    raw = load_dataset(dataset_id)
    if raw["source"] != "youtube":
        raise ValueError(f"Can only clean youtube datasets, got '{raw['source']}'")
    rows = [clean_row(row, raw["pulled_at"]) for row in raw["rows"]]
    return save_dataset(rows, "clean", derived_from=dataset_id, pulled_at=raw["pulled_at"])