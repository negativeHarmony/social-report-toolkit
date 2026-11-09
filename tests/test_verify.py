from social_report_toolkit.verify import (
    account_aliases, build_facts, check_narrative, extract_numbers, find_matches, sentence_around,
)


def numbers(videos, views, rate):
    return {"videos": videos, "total_views": views, "median_views_per_day": None,
            "videos_in_views_per_day": 0, "engagement_rate": rate, "videos_in_engagement_rate": videos}


SUMMARY = {
    "overall": numbers(20, 3_000_000, 0.0296),
    "by_account": [
        {"account_name": "The Late Show with Stephen Colbert", **numbers(10, 2_000_000, 0.0342)},
        {"account_name": "The Tonight Show Starring Jimmy Fallon", **numbers(10, 1_000_000, 0.0274)},
    ],
    "by_format": [],
    "by_day": [{"posted_day": "Tuesday", **numbers(2, 50_000, 0.0622)}],
}
FACTS = build_facts(SUMMARY)


def verdicts(text):
    return [(c.number, c.verdict) for c in check_narrative(text, FACTS)]


# --- Finding numbers ---

def test_dates_and_times_are_not_metrics():
    found = extract_numbers("Posted 2026-11-06 at 11pm and 23:00, 30 videos")
    assert [m.text for m in found] == ["30"]


def test_units_are_read():
    found = extract_numbers("42.4 million, 21.7K, 3.42%")
    assert [(m.number, m.unit) for m in found] == [(42.4, "million"), (21.7, "k"), (3.42, "%")]


def test_decimal_point_is_not_a_sentence_end():
    text = "Colbert led at 3.42%. Fallon trailed."
    assert sentence_around(text, text.index("3.42")) == "Colbert led at 3.42%."


# --- Matching numbers ---

def test_rounded_value_matches():
    mention = extract_numbers("3.4%")[0]
    assert [f.subject for f in find_matches(mention, FACTS)] == ["The Late Show with Stephen Colbert"]


def test_wrong_rounding_is_not_found():
    assert verdicts("Colbert reached 3.5%.") == [("3.5%", "not_found")]


def test_percent_never_matches_a_count():
    assert verdicts("Colbert posted 10%.") == [("10%", "not_found")]


def test_shared_name_word_is_not_an_alias():
    aliases = account_aliases(["The Tonight Show Starring Jimmy Fallon", "Jimmy Kimmel Live"])
    assert aliases == {"The Tonight Show Starring Jimmy Fallon": ["fallon"], "Jimmy Kimmel Live": ["kimmel"]}


# --- Verdicts ---

def test_correct_attribution_is_verified():
    assert verdicts("Colbert led at 3.42%.") == [("3.42%", "verified")]


def test_swapped_number_is_caught():
    assert verdicts("Fallon led at 3.42%.") == [("3.42%", "wrong_subject")]


def test_vague_claim_is_flagged():
    assert verdicts("One day reached 6.22%.") == [("6.22%", "unclear_subject")]


def test_overall_figure_next_to_a_named_subject():
    assert verdicts("Colbert beat the average of 2.96%.") == [("2.96%", "verified")]