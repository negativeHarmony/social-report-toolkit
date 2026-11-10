# social-report-toolkit

An MCP server that lets an AI agent (Claude, Hermes or any MCP client) pull YouTube channel
performance data, clean it into analysis-ready metrics, build a client-ready Excel + PowerPoint
report, and write a narrative whose **every number is checked against the data in code**.
It can also sort a video's comments into themes, with a **blind human review that measures how
often the AI's labels are right**.

A complete AI-assisted social media reporting pipeline:
**pull** → **clean** → **report** → **narrate** → **verify**, plus **comment themes**.

## Why it's built this way

LLMs are good at deciding what to do, reading text for meaning and writing clearly, but bad at
copying large tables of numbers exactly, and they can be confidently wrong. So:

- **The data never passes through the model.** Tools pass dataset IDs, and every number is
  fetched, stored and calculated in code.
- **When the model does write numbers** (in a narrative), code checks every one of them before
  the narrative reaches a person.
- **When the model has to judge meaning** (theming comments), a person checks a random sample
  blind, and code measures how often the model was right.

```
AI → pull_youtube(["@fallontonight", ...])  → youtube_<timestamp>    (raw dataset)
AI → clean_dataset("youtube_<timestamp>")    → clean_<timestamp>      (cleaned dataset)
AI → build_report("clean_<timestamp>")       → .xlsx + .pptx paths    (report)
AI → get_report_facts("clean_<timestamp>")   → summary numbers + definitions + writing rules
AI   writes a narrative
AI → check_narrative("clean_<timestamp>", narrative)  → a verdict for every number
AI   fixes every problem and checks again before showing the narrative
AI → export_csv(any dataset_id)              → path to a CSV          (optional)
```

## Data accuracy

- **Hidden likes and disabled comments are stored as blank, never 0.** "Hidden" and "zero" are
  different facts, and treating them as 0 would distort averages and engagement rates.
- **Every dataset records when its numbers were pulled** (UTC), and every derived dataset records
  the dataset it came from, so any number can be traced back to its raw pull in `data/raw/`.
- **`is_short_form` is an approximation.** The YouTube API has no "is a Short" field, so videos
  of 180 seconds or less are flagged. This also catches short regular videos.
- **Up to 50 recent videos per channel** (one API page), taken from the channel's uploads playlist.
  Channels that post at different rates cover different time spans, so compare rates
  (engagement, views per day) rather than totals across channels.

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

## Reports

`build_report` turns a **cleaned** dataset into two files with matching names in `data/reports/`.

**Excel workbook** (`report_<dataset_id>.xlsx`)
- **Summary**: period, pull time and source datasets, then four tables: overall, by account,
  by format, and by posting day (Monday → Sunday, US Eastern)
- **Charts**: engagement rate by account, and median views per day by posting day. Native Excel
  charts that read directly from the Summary tables.
- **All videos**: every cleaned row, with frozen headers and filters

**PowerPoint deck** (`report_<dataset_id>.pptx`), 5 slides
1. Title, period and pull time
2. At a glance: headline numbers, each with the number of videos it is based on
3. By account (table)
4. Engagement rate by account (chart)
5. Median views per day by posting day (chart, with the number of videos behind each bar)

Both files are built from the same calculation in the same run, so their numbers always match.

### How the summary numbers are calculated

| Number | Method |
|---|---|
| Engagement rate (per group) | Total (likes + comments) ÷ total views, over videos with complete counts. **Weighted**, so a tiny video can't outweigh a large one, unlike averaging each video's rate. |
| Median views per day | The middle value, so one viral video can't distort what a typical video does. Videos under 1 day old are excluded. |
| Total views | Sum of all known view counts. |
| Base counts | Every average reports how many videos it was calculated from ("Videos in engagement rate", "Videos in views/day"), so thin groups are visible. |

## Narrative and verification

`get_report_facts` gives the agent the report's summary numbers (the same ones as the Excel and
PowerPoint files), plain-English definitions, and writing rules: use only these numbers, one
claim per sentence naming its channel, format or day, and round without inventing precision.

`check_narrative` then finds every number in the narrative, works out which sentence it is in and
which channel, format or day that sentence names, and gives it a verdict:

| Verdict | Meaning | Example |
|---|---|---|
| `verified` | A correct rounding of a real value, attributed to the right subject | "Colbert led at 3.42%" |
| `wrong_subject` | A real value, but it belongs to a different subject (the result says whose) | "Fallon led at 3.42%" when 3.42% is Colbert's |
| `unclear_subject` | A real value, but the sentence doesn't say whose it is | "One day reached 6.2%" |
| `not_found` | Not in the data: invented, or wrongly rounded | "Engagement hit 8.1%" |

**How matching works**
- **Rounding is judged by the digits written.** "3.4%" is correct for a true 3.42%, but "3.5%" and
  "3.43%" are not. Writing more decimals claims more precision and is held to it.
- **Percentages only match rates**, and counts only match counts.
- **Units are understood**: `42.4 million`, `21.7K`, `3.42%`, `42,350,498`.
- **Dates and clock times are skipped** (`2026-11-06`, `11pm`, `23:00`); they are not metrics.
- **Subjects are recognised by their distinctive words.** Words shared by several channel names
  (like "Jimmy" in Fallon and Kimmel) and generic TV words are never used to identify a channel.

**Known limitation:** if one sentence names two subjects, a number belonging to either one passes.
The writing rule "one claim per sentence" avoids this.

## Comment themes, with a blind human review

Sorting comments by meaning is a job only the model can do, so instead of trusting its labels,
the toolkit **measures** them:

```
AI → pull_comments(video link or ID)          → comments_<timestamp>   (up to 500 comments)
AI → get_comments_page(id, offset)            → reads every comment, 50 at a time
AI   chooses 3–9 themes, each with a one-line definition, and labels every comment
AI → save_comment_labels(id, themes, labels)  → labelled_<timestamp> + theme counts (code)
AI → create_review_sheet(labelled id)         → a blind review sheet for a person
     The person labels 30 random comments without seeing the AI's labels
AI → score_comment_review(labelled id)        → agreement rate, likely range, disagreements (code)
```

**Comments**
- **Top-level comments only**, in YouTube's relevance order (most liked and discussed first). Replies
  are counted but not themed. This is **not a random sample** of all viewers, and results should
  say so.
- **Author names are not stored.** Only what the analysis needs is kept.
- Links in any format work: `watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`, `/live/`, or a bare ID.

**Themes and labels** (checked in code before saving)
- Every theme needs a **one-line definition**, so labels (the AI's and the reviewer's) are applied
  consistently. Vague themes make even people disagree with themselves.
- An **"Other"** theme is always added, so comments that fit nowhere aren't forced into a real theme.
- At most 10 themes, no duplicates, and no commas in theme names.
- **Every comment gets exactly one label**, from the theme list. Missing, invented or off-list
  labels are refused. Labels are matched by comment ID, never by position.
- **Theme counts** (comments, share and likes per theme) are calculated in code, including themes
  with zero comments.

**The review**
- **Random**: 30 comments chosen at random. The random seed is recorded on the sheet, so the
  sample can be reproduced.
- **Blind**: the AI's labels are not in the file at all, so they can't influence the reviewer.
  The AI is also told not to show individual labels before the review is done.
- **Dropdowns** with the theme list and definitions. Answers are checked in code anyway, so
  blank or off-list answers are refused whatever spreadsheet app was used.
- **Never overwritten**: a second review sheet for the same dataset is refused, so a
  half-finished review can't be lost.

**The score**
- **Agreement rate**: the share of reviewed comments where the reviewer and the AI chose the same theme.
- **Likely range (95%)**: a Wilson score interval for the true agreement rate. With only 30
  comments, a measured 80% could plausibly be anywhere from about 63% to 90%; the range says so.
- **Agreement per AI theme**, to show which themes the AI handles well or badly.
- **Every disagreement**, with the comment and both labels.

## Tools

| Tool | Input | Returns |
|---|---|---|
| `pull_youtube` | `handles`: 1–10 channel handles (e.g. `"@fallontonight"`), `limit`: videos per channel (1–50, default 50) | `dataset_id`, total videos, videos per channel, counts of hidden likes / comments off |
| `clean_dataset` | `dataset_id` from `pull_youtube` | New `dataset_id`, the raw ID it came from, row count, counts of blank metrics, date range of posts |
| `build_report` | `dataset_id` from `clean_dataset` | Full paths of the Excel and PowerPoint files, number of videos and accounts |
| `get_report_facts` | `dataset_id` from `clean_dataset` | Period, pull time, definitions, writing rules and the summary numbers |
| `check_narrative` | `dataset_id` from `clean_dataset`, `narrative` text (max 20,000 characters) | Numbers checked, `all_verified`, counts per verdict, and each problem with its sentence and what it actually matches |
| `pull_comments` | `video`: a YouTube link or ID, `limit`: 1–500 comments (default 200) | `dataset_id`, video title, comment count, replies not included |
| `get_comments_page` | `dataset_id` from `pull_comments`, `offset` (default 0) | Up to 50 comments (ID, text, likes), the total, and `next_offset` (null when done) |
| `save_comment_labels` | `dataset_id` from `pull_comments`, `themes` (name → definition), `labels` (comment ID → theme) | New `dataset_id` and theme counts calculated in code |
| `create_review_sheet` | `dataset_id` from `save_comment_labels` | Full path of the blind review sheet |
| `score_comment_review` | `dataset_id` from `save_comment_labels` | Reviewed, agreed, agreement rate, likely range, agreement per theme, disagreements |
| `export_csv` | `dataset_id` (raw, cleaned or comments) | Full path of the CSV and its row count |

**Safety:** dataset IDs are validated against a strict pattern, so a tool call can't read or write
files outside the data folder. API errors are passed back with the API key redacted.

### Output folders

```
data/
├── raw/       ← datasets (JSON): youtube_..., clean_..., comments_..., labelled_...
├── exports/   ← CSVs from export_csv
├── reports/   ← Excel + PowerPoint from build_report
└── reviews/   ← blind review sheets from create_review_sheet
```

### CSV columns

**Raw** (`youtube_...csv`): `pulled_at`, `channel_handle`, `channel_title`, `video_id`, `title`,
`published_at` (UTC), `duration_seconds`, `is_short_form`, `views`, `likes`, `comments`

**Cleaned** (`clean_...csv`): `pulled_at`, `platform`, `account_handle`, `account_name`, `post_id`,
`title`, `published_at_utc`, `posted_local`, `posted_day`, `posted_hour`, `format`,
`duration_seconds`, `views`, `likes`, `comments`, `engagement_rate`, `age_days`, `views_per_day`

**Comments** (`comments_...csv`): `pulled_at`, `video_id`, `video_title`, `comment_id`, `text`,
`likes`, `replies`, `published_at`

## Setup

### 1. Get a YouTube API key (free)

1. In [Google Cloud Console](https://console.cloud.google.com), create a project.
2. Enable **YouTube Data API v3**.
3. APIs & Services → Credentials → Create credentials → **API key**.
4. Restrict the key to **YouTube Data API v3**.

The free quota is 10,000 units a day. A video pull costs about 3 units per channel, and a comment
pull about 1 unit per 100 comments.

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
> Pull the last 50 videos from @fallontonight, @ColbertLateShow and @JimmyKimmelLive, clean the data, build a report, and write a short summary of the results. Check every number before showing it to me.

> Pull 200 comments from this trailer: <link>. Sort them into themes, then make me a blind review sheet so I can check your labels.

### Updating

If you installed with `pip install .`, reinstall after pulling new changes:

```bash
git pull
pip install .
```

Then restart your agent so it starts the updated server.

## Try it without an agent

`scripts/try_mcp.py` starts the server and runs pull → clean → facts → check, the way an agent
would, using a deliberately flawed narrative so you can see the verdicts:

```bash
python scripts/try_mcp.py
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest -v
```

The tests check:
- **Cleaning rules**: engagement rate, US Eastern posting times with daylight saving, views per day,
  age measured at pull time, hidden counts kept blank
- **The narrative checker**: dates and times skipped, units read, sentence splitting around decimals,
  rounding judged by the digits written, percentages never matching counts, shared name words never
  used as aliases, and each verdict, including catching a number attributed to the wrong channel
- **Comment themes**: every YouTube link format, theme-list rules, complete and valid labels, theme
  counts including unused themes, a blind and correctly sized review sheet that is never
  overwritten, blank and off-list answers refused, agreement counting and the likely range
- **The MCP server**, through a real client connection: the tool list, the channel limit and the
  dataset-ID path check

## Roadmap

- [x] Stage 1: pull YouTube data and export to CSV
- [x] Stage 2: clean and normalise (engagement rate, posting day/hour, views per day)
- [x] Stage 3: one-click Excel and PowerPoint report
- [x] Stage 4: AI-written narrative from the report's numbers
- [x] Stage 5: automatic check of every number in the narrative against the source data
- [x] Comment themes with a blind human review and measured agreement
- [ ] Optional date range, so every channel is compared over the same period

## License

MIT
