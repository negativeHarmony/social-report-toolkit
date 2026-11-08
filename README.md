# social-report-toolkit

An MCP server that lets an AI agent (Claude, Hermes or any MCP client) pull YouTube channel
performance data, clean it into analysis-ready metrics and export it to CSV,
**without the model ever handling the numbers**.

Stages 1–2 of an AI-assisted social media reporting pipeline: **pull** → **clean** → report → narrate → verify.

## Why it's built this way

LLMs are good at deciding what to do and bad at copying large tables of numbers exactly.
So the tools never send the data through the model:

```
AI → pull_youtube(["@fallontonight", ...])  → youtube_<timestamp>   (raw)
AI → clean_dataset("youtube_<timestamp>")    → clean_<timestamp>     (cleaned)
AI → export_csv("clean_<timestamp>")         → path to the CSV
```

Each step passes a dataset ID, never the data. The model orchestrates; the numbers go
YouTube → JSON → cleaned JSON → CSV untouched.

## Data accuracy

- **Hidden likes and disabled comments are stored as blank, never 0.** "Hidden" and "zero" are
  different facts, and treating them as 0 would distort averages and engagement rates.
- **Every dataset records when its numbers were pulled** (UTC), and each CSV keeps its dataset's ID,
  so any number can be traced back to its raw pull in `data/raw/`.
- **`is_short_form` is an approximation.** The YouTube API has no "is a Short" field, so videos
  of 180 seconds or less are flagged. This also catches short regular videos.
- **Up to 50 recent videos per channel** (one API page), taken from the channel's uploads playlist.

## Cleaned metrics

`clean_dataset` adds these columns. The raw dataset is never changed, and every cleaned dataset
records the raw dataset it came from (`derived_from`) and when its numbers were pulled.

| Column | Definition |
|---|---|
| `engagement_rate` | (likes + comments) ÷ views, as a fraction (0.0267 = 2.67%). Blank if likes or comments are hidden, or views are 0. |
| `views_per_day` | views ÷ age in days. Blank for videos under 1 day old. A lifetime average, so it still flatters newer videos somewhat. |
| `age_days` | Days from posting to when the data was **pulled** (not when it was cleaned). |
| `posted_local`, `posted_day`, `posted_hour` | Posting time in **US Eastern** (America/New_York), with daylight saving applied. |
| `format` | `short_form` (≤ 180 s) or `long_form`. |
| `platform`, `account_handle`, `account_name`, `post_id` | Platform-neutral names, so other platforms can share the same table later. |

## Tools

| Tool | Input | Returns |
|---|---|---|
| `pull_youtube` | `handles`: 1–10 channel handles (e.g. `"@fallontonight"`), `limit`: videos per channel (1–50, default 50) | `dataset_id`, total videos, videos per channel, counts of hidden likes / comments off |
| `clean_dataset` | `dataset_id` from `pull_youtube` | New `dataset_id`, the raw ID it came from, row count, counts of blank metrics, date range of posts |
| `export_csv` | `dataset_id` (raw or cleaned) | Full path of the CSV and its row count |

**Safety:** dataset IDs are validated against a strict pattern, so a tool call can't read or write
files outside the data folder. API errors are passed back with the API key redacted.

### CSV columns

**Raw** (`youtube_...csv`): `pulled_at`, `channel_handle`, `channel_title`, `video_id`, `title`,
`published_at` (UTC), `duration_seconds`, `is_short_form`, `views`, `likes`, `comments`

**Cleaned** (`clean_...csv`): `pulled_at`, `platform`, `account_handle`, `account_name`, `post_id`,
`title`, `published_at_utc`, `posted_local`, `posted_day`, `posted_hour`, `format`,
`duration_seconds`, `views`, `likes`, `comments`, `engagement_rate`, `age_days`, `views_per_day`

## Setup

### 1. Get a YouTube API key (free)

1. In [Google Cloud Console](https://console.cloud.google.com), create a project.
2. Enable **YouTube Data API v3**.
3. APIs & Services → Credentials → Create credentials → **API key**.
4. Restrict the key to **YouTube Data API v3**.

The free quota is 10,000 units a day; a pull costs about 3 units per channel.

### 2. Install

```bash
git clone https://github.com/negativeHarmony/social-report-toolkit.git
cd social-report-toolkit
python3 -m venv .venv
source .venv/bin/activate
pip install .
cp .env.example .env   # then add your API key
```

Requires Python 3.10+.

### 3. Connect to an AI agent

The server uses the **stdio** transport. Use absolute paths, and set `TOOLKIT_DATA_DIR`
so files land in a known folder whatever directory the agent starts the server from.

**Claude Code**

```bash
claude mcp add --scope user \
  --env YOUTUBE_API_KEY=your-api-key \
  --env TOOLKIT_DATA_DIR=/absolute/path/to/social-report-toolkit/data \
  social-report-toolkit \
  -- /absolute/path/to/social-report-toolkit/.venv/bin/social-report-mcp
```

**Claude Desktop** (`claude_desktop_config.json`, then restart Claude)

```json
{
  "mcpServers": {
    "social-report-toolkit": {
      "command": "/absolute/path/to/social-report-toolkit/.venv/bin/social-report-mcp",
      "env": {
        "YOUTUBE_API_KEY": "your-api-key",
        "TOOLKIT_DATA_DIR": "/absolute/path/to/social-report-toolkit/data"
      }
    }
  }
}
```

**Other MCP clients:** run `social-report-mcp` with the same environment variables.

Then ask, for example:
> Pull the last 50 videos from @fallontonight, @ColbertLateShow and @JimmyKimmelLive, clean the data and give me a CSV.

### Updating

If you installed with `pip install .`, reinstall after pulling new changes:

```bash
git pull
pip install .
```

Then restart your agent so it starts the updated server.

## Try it without an agent

`scripts/try_mcp.py` starts the server and calls all three tools in order, the way an agent would:

```bash
python scripts/try_mcp.py
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest -v
```

The tests check the cleaning rules (engagement rate, US Eastern posting times with daylight
saving, views per day, age measured at pull time, hidden counts kept blank) and, through a real
MCP client connection, the tool list, the channel limit and the dataset-ID path check.

## Roadmap

- [x] Stage 1: pull YouTube data and export to CSV
- [x] Stage 2: clean and normalise (engagement rate, posting day/hour, views per day)
- [ ] Stage 3: one-click Excel and PowerPoint report
- [ ] Stage 4: AI-written narrative
- [ ] Stage 5: automatic check of every number in the narrative against the source data

## License

MIT
