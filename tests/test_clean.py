from social_report_toolkit.clean import clean_row, engagement_rate, posting_time, views_per_day

RAW = {
    "channel_handle": "@fallontonight", "channel_title": "The Tonight Show",
    "video_id": "aBc123", "title": "Charades", "published_at": "2026-11-03T04:00:00Z",
    "duration_seconds": 402, "is_short_form": False,
    "views": 481203, "likes": 12044, "comments": 803,
}
PULLED_AT = "2026-11-06T16:00:00+00:00"


def test_engagement_rate_formula():
    assert engagement_rate(1800, 200, 50000) == 0.04


def test_engagement_rate_unknown_when_likes_hidden():
    assert engagement_rate(None, 200, 50000) is None


def test_engagement_rate_unknown_when_no_views():
    assert engagement_rate(0, 0, 0) is None


def test_posting_day_uses_us_eastern_not_utc():
    result = posting_time("2026-11-06T04:00:00Z")
    assert result["posted_day"] == "Thursday"
    assert result["posted_hour"] == 23


def test_daylight_saving_is_applied():
    assert posting_time("2026-07-15T03:30:00Z")["posted_local"].endswith("-04:00")


def test_views_per_day_formula():
    assert views_per_day(481203, 3.5) == 137486.6


def test_views_per_day_blank_under_one_day():
    assert views_per_day(5000, 0.25) is None


def test_clean_row_measures_age_at_pull_time():
    assert clean_row(RAW, PULLED_AT)["age_days"] == 3.5


def test_clean_row_keeps_hidden_likes_blank():
    row = clean_row({**RAW, "likes": None}, PULLED_AT)
    assert row["likes"] is None
    assert row["engagement_rate"] is None


def test_clean_row_format_label():
    assert clean_row({**RAW, "is_short_form": True}, PULLED_AT)["format"] == "short_form"