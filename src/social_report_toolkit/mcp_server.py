"""MCP server: lets an AI agent pull YouTube stats and export them, without handling the numbers itself."""
from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from .datasets import load_dataset, save_dataset
from .export import export_csv as write_csv
from .youtube import pull_channel

MAX_CHANNELS = 10

mcp = MCPServer("social-report-toolkit")


def _api_key() -> str:
    load_dotenv()
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is not set")
    return key


@mcp.tool()
def pull_youtube(handles: List[str], limit: int = 50) -> dict:
    """Pull the most recent videos (title, publish date, duration, views, likes, comments)
    for 1-10 YouTube channels and save them as a dataset. Pass channel handles like
    "@fallontonight". limit = videos per channel (1-50, default 50).
    Returns a dataset_id and a summary, not the data itself. Pass the dataset_id to
    export_csv to get a CSV. Hidden like counts and disabled comments are stored as
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
def export_csv(dataset_id: str) -> dict:
    """Write a saved dataset (from pull_youtube) to a CSV file that opens in Excel.
    Returns the full path of the CSV and its row count."""
    path = write_csv(dataset_id)
    rows = len(load_dataset(dataset_id)["rows"])
    return {"csv_path": str(path.resolve()), "rows": rows}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()