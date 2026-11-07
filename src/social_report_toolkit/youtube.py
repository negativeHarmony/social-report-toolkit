"""Pulls recent video stats for YouTube channels via the YouTube Data API v3."""
from __future__ import annotations

import re
from typing import List, Optional

import requests

API = "https://www.googleapis.com/youtube/v3"
SHORT_FORM_MAX_SECONDS = 180 #distinguish shot form and long form videos

def _get(endpoint: str, api_key: str, **params) -> dict:
    params["key"] = api_key
    response = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
    if response.status_code != 200:
        message = response.json().get("error", {}).get("message", response.text)
        raise RuntimeError(f"YouTube API {endpoint} failed ({response.status_code}): {message}")
    return response.json()


# helper function to convert video duration iso format into seconds 
def parse_duration(iso: str) -> int:
    """Convert YouTube's ISO 8601 duration, e.g. 'PT1H2M3S', into seconds (3723)."""
    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not match:
        raise ValueError(f"Unrecognised duration: {iso}")
    days, hours, minutes, seconds = (int(x) if x else 0 for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds

#helper function to return int value of stats or None if stat ommited
def _optional_int(stats: dict, key: str) -> Optional[int]:
    value = stats.get(key)
    return int(value) if value is not None else None

#find the playlist ID for the channel uploads
def get_channel(handle: str, api_key: str) -> dict:
    data = _get("channels", api_key, part="snippet,contentDetails", forHandle=handle)
    items = data.get("items", [])
    if not items:
        raise ValueError(f"No channel found for handle {handle}")
    channel = items[0]
    return {
        "title": channel["snippet"]["title"],
        "uploads_playlist": channel["contentDetails"]["relatedPlaylists"]["uploads"],
    }
    
#get the individual video ids 
def get_recent_video_ids(playlist_id: str, api_key: str, limit: int = 50) -> List[str]:
    data = _get("playlistItems", api_key, part="contentDetails",
                playlistId=playlist_id, maxResults=min(limit, 50))
    return [item["contentDetails"]["videoId"] for item in data.get("items", [])]

#get get the video stats, snippet and content details for each video and store in a list
def get_videos(video_ids: List[str], api_key: str) -> List[dict]:
    if not video_ids:
        return []
    data = _get("videos", api_key, part="snippet,statistics,contentDetails", id=",".join(video_ids))
    rows = []
    for video in data.get("items", []):
        stats = video.get("statistics", {})
        seconds = parse_duration(video["contentDetails"]["duration"])
        rows.append({
            "video_id": video["id"],
            "title": video["snippet"]["title"],
            "published_at": video["snippet"]["publishedAt"],
            "duration_seconds": seconds,
            "is_short_form": seconds <= SHORT_FORM_MAX_SECONDS,
            "views": _optional_int(stats, "viewCount"),
            "likes": _optional_int(stats, "likeCount"),
            "comments": _optional_int(stats, "commentCount"),
        })
    return rows

#chain functions together
def pull_channel(handle: str, api_key: str, limit: int = 50) -> List[dict]:
    channel = get_channel(handle, api_key)
    video_ids = get_recent_video_ids(channel["uploads_playlist"], api_key, limit)
    return [
        {"channel_handle": handle, "channel_title": channel["title"], **video}
        for video in get_videos(video_ids, api_key)
    ]