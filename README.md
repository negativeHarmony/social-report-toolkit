# social-report-toolkit

An MCP server that lets an AI agent (Claude, Hermes or any MCP client) pull YouTube channel
performance data and export it to CSV, **without the model ever handling the numbers**.

Stage 1 of an AI-assisted social media reporting pipeline: **pull** → clean → report → narrate → verify.

## Why it's built this way

LLMs are good at deciding what to do and bad at copying large tables of numbers exactly.
So the tools never send the data through the model:

```
AI → pull_youtube(["@fallontonight", ...])
       server fetches from YouTube, saves the rows to disk,
       returns only a dataset_id and a short summary

AI → export_csv(dataset_id)
       server writes the CSV from the saved rows, returns its path
```

The model orchestrates; the numbers go YouTube → JSON → CSV untouched.

## Data accuracy

- **Hidden likes and disabled comments are stored as blank, never 0.** "Hidden" and "zero" are
  different facts, and treating them as 0 would distort averages and engagement rates.
- **Every dataset records when it was pulled** (UTC), and each CSV keeps its dataset's ID,
  so any number can be traced back to its raw pull in `data/raw/`.
- **`is_short_form` is an approximation.** The YouTube API has no "is a Short" field, so videos
  of 180 seconds or less are flagged. This also catches short regular videos.
- **Up to 50 recent videos per channel** (one API page), taken from the channel's uploads playlist.

## Tools

| Tool | Input | Returns |
|---|---|---|
| `pull_youtube` | `handles`: 1–10 channel handles (e.g. `"@fallontonight"`), `limit`: videos per channel (1–50, default 50) | `dataset_id`, total videos, videos per channel, counts of hidden 
likes / comments off |
| `export_csv` | `dataset_id` from `pull_youtube` | Full path of the CSV and its row count |

**Safety:** dataset IDs are validated against a strict pattern, so a tool call can't read or write
files outside the data folder. API errors are passed back with the API key redacted.

### CSV columns

`pulled_at`, `channel_handle`, `channel_title`, `video_id`, `title`, `published_at` (UTC),
`duration_seconds`, `is_short_form`, `views`, `likes`, `comments`

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
> Pull the last 50 videos from @fallontonight, @ColbertLateShow and @JimmyKimmelLive and give me a CSV.

## Try it without an agent

`scripts/try_mcp.py` starts the server and calls both tools the way an agent would:

```bash
python scripts/try_mcp.py
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest -v
```

The tests check duration parsing, hidden-count handling, and, through a real MCP client
connection, the tool list, the channel limit and the dataset-ID path check.

## Roadmap

- [x] Stage 1: pull YouTube data and export to CSV
- [ ] Stage 2: clean and normalise (engagement rate, posting day/hour)
- [ ] Stage 3: one-click Excel and PowerPoint report
- [ ] Stage 4: AI-written narrative
- [ ] Stage 5: automatic check of every number in the narrative against the source data

## License

MIT
