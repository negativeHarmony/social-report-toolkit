"""Stage 3: turn cleaned rows into summary numbers for reports. All maths happens here, in code."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional
from statistics import median


def group_by(rows: List[dict], key: str) -> Dict[str, List[dict]]:
    """Split rows into groups that share the same value for `key`."""
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return dict(groups)

"""
result
group_by(rows, "format")
# →>
{
    "long_form":  [row1, row3, row4],
    "short_form": [row2, row5],
}
"""

def summarise(rows: List[dict]) -> dict:
    """Report numbers for any group of cleaned rows. Blanks are left out, never counted as 0."""
    views = [row["views"] for row in rows if row["views"] is not None]
    speeds = [row["views_per_day"] for row in rows if row["views_per_day"] is not None]
    complete = [row for row in rows if row["engagement_rate"] is not None]

    engaged = sum(row["likes"] + row["comments"] for row in complete)
    watched = sum(row["views"] for row in complete)

    return {
        "videos": len(rows),
        "total_views": sum(views),
        "median_views_per_day": round(median(speeds), 1) if speeds else None,
        "videos_in_views_per_day": len(speeds), #how many videos the mean, median views per day is calculated from
        "engagement_rate": round(engaged / watched, 4) if complete else None,
        "videos_in_engagement_rate": len(complete), #how many videos engagement rate is actually calculated from
    }
    
    
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def breakdown(rows: List[dict], key: str, order: Optional[List[str]] = None) -> List[dict]:
    """Summarise rows per value of `key`, one result per group, in a sensible order."""
    groups = group_by(rows, key)
    names = order if order else sorted(groups)
    return [{key: name, **summarise(groups[name])} for name in names if name in groups]


def build_summary(rows: List[dict]) -> dict:
    """Everything the report shows: overall numbers plus the three breakdowns."""
    return {
        "overall": summarise(rows),
        "by_account": breakdown(rows, "account_name"),
        "by_format": breakdown(rows, "format"),
        "by_day": breakdown(rows, "posted_day", DAY_ORDER),
    }