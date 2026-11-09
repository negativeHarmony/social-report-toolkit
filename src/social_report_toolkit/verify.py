"""Stage 5: check every number in an AI-written narrative against the source data."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

NUMBER = re.compile(
    r"(?<![\w.])"
    r"(?P<whole>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<frac>\d+))?"
    r"\s?(?P<unit>%|percent\b|thousand\b|million\b|billion\b|[KMB]\b)?",
    re.IGNORECASE,
)

NOT_A_METRIC = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:T[\d:]+(?:Z|[+-]\d{2}:\d{2})?)?"
    r"|\b\d{1,2}:\d{2}\b"
    r"|\b\d{1,2}\s?(?:am|pm)\b",
    re.IGNORECASE,
)


@dataclass
class Mention:
    text: str
    number: float
    decimals: int
    unit: str
    start: int


def _skipped_spans(text: str) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in NOT_A_METRIC.finditer(text)]


def extract_numbers(text: str) -> List[Mention]:
    """Find every metric-like number in the text, skipping dates and clock times."""
    skipped = _skipped_spans(text)
    mentions = []
    for m in NUMBER.finditer(text):
        if any(start <= m.start() < end for start, end in skipped):
            continue
        whole = m.group("whole").replace(",", "")
        frac = m.group("frac") or ""
        mentions.append(Mention(
            text=m.group(0).strip(),
            number=float(f"{whole}.{frac}" if frac else whole),
            decimals=len(frac),
            unit=(m.group("unit") or "").lower(),
            start=m.start(),
        ))
    return mentions

MULTIPLIERS = {
    "k": 1_000, "thousand": 1_000,
    "m": 1_000_000, "million": 1_000_000,
    "b": 1_000_000_000, "billion": 1_000_000_000,
}
PERCENT_UNITS = {"%", "percent"}


def to_value(mention: Mention) -> Tuple[float, bool]:
    """Convert a mention into the data's form. Returns (value, is_percent)."""
    if mention.unit in PERCENT_UNITS:
        return mention.number / 100, True
    return mention.number * MULTIPLIERS.get(mention.unit, 1), False


def precision(mention: Mention) -> float:
    """The size of the last digit the writer used, in the data's form."""
    step = 10 ** -mention.decimals
    if mention.unit in PERCENT_UNITS:
        return step / 100
    return step * MULTIPLIERS.get(mention.unit, 1)


METRIC_IS_PERCENT = {
    "videos": False,
    "total_views": False,
    "median_views_per_day": False,
    "videos_in_views_per_day": False,
    "engagement_rate": True,
    "videos_in_engagement_rate": False,
}
STOP_WORDS = {"the", "with", "and", "show", "live", "late", "night", "tonight", "starring"}
FORMAT_ALIASES = {
    "long_form": ["long-form", "long form"],
    "short_form": ["short-form", "short form", "shorts"],
}


@dataclass
class Fact:
    subject: str
    aliases: List[str]
    metric: str
    value: float
    is_percent: bool


def account_aliases(names: List[str]) -> Dict[str, List[str]]:
    """Words that identify each account on its own: in its name, in no other account's name."""
    words = {name: {w.lower() for w in re.findall(r"[A-Za-z]+", name)} for name in names}
    aliases = {}
    for name, own in words.items():
        others = set().union(*(w for other, w in words.items() if other != name))
        aliases[name] = sorted(w for w in own - others - STOP_WORDS if len(w) >= 4)
    return aliases


def _facts_for(subject: str, aliases: List[str], numbers: dict) -> List[Fact]:
    return [
        Fact(subject, aliases, metric, numbers[metric], is_percent)
        for metric, is_percent in METRIC_IS_PERCENT.items()
        if numbers[metric] is not None
    ]


def build_facts(summary: dict) -> List[Fact]:
    """Every number the report contains, labelled with what it is and who it belongs to."""
    facts = _facts_for("all videos", [], summary["overall"])
    facts.append(Fact("all videos", [], "accounts", len(summary["by_account"]), False))

    names = [row["account_name"] for row in summary["by_account"]]
    aliases = account_aliases(names)
    for row in summary["by_account"]:
        facts += _facts_for(row["account_name"], aliases[row["account_name"]], row)
    for row in summary["by_format"]:
        facts += _facts_for(row["format"], FORMAT_ALIASES.get(row["format"], []), row)
    for row in summary["by_day"]:
        facts += _facts_for(row["posted_day"], [row["posted_day"].lower()], row)
    return facts

TOLERANCE = 1e-9


def matches(mention: Mention, fact: Fact) -> bool:
    """True if the written number is a correct rounding of the fact's value."""
    value, is_percent = to_value(mention)
    if is_percent != fact.is_percent:
        return False
    return abs(fact.value - value) <= precision(mention) / 2 + TOLERANCE


def find_matches(mention: Mention, facts: List[Fact]) -> List[Fact]:
    """Every fact this written number could correctly refer to."""
    return [fact for fact in facts if matches(mention, fact)]

SENTENCE_END = re.compile(r"[.!?](?=\s|$)|\n")
OVERALL_WORDS = ["overall", "average", "across", "total", "combined", "all"]


@dataclass
class Check:
    number: str
    sentence: str
    verdict: str
    facts: List[str]


def sentence_around(text: str, position: int) -> str:
    """The sentence that contains the character at `position`."""
    start = 0
    for m in SENTENCE_END.finditer(text):
        if m.end() <= position:
            start = m.end()
        else:
            return text[start:m.end()].strip()
    return text[start:].strip()


def _names(word: str, sentence: str) -> bool:
    return re.search(rf"\b{re.escape(word)}s?\b", sentence) is not None


def _describe(fact: Fact) -> str:
    return f"{fact.subject}: {fact.metric}"


def check_number(mention: Mention, text: str, facts: List[Fact]) -> Check:
    sentence = sentence_around(text, mention.start)
    lower = sentence.lower()
    candidates = find_matches(mention, facts)
    named = {f.subject for f in facts if any(_names(alias, lower) for alias in f.aliases)}
    about_overall = not named or any(_names(word, lower) for word in OVERALL_WORDS)

    if not candidates:
        return Check(mention.text, sentence, "not_found", [])
    verified = [f for f in candidates
                if f.subject in named or (f.subject == "all videos" and about_overall)]
    if verified:
        return Check(mention.text, sentence, "verified", [_describe(f) for f in verified])
    verdict = "wrong_subject" if named else "unclear_subject"
    return Check(mention.text, sentence, verdict, [_describe(f) for f in candidates])


def check_narrative(text: str, facts: List[Fact]) -> List[Check]:
    """A verdict for every metric-like number in the narrative."""
    return [check_number(m, text, facts) for m in extract_numbers(text)]


"""
limitation: if a sentence names two subjects (“Colbert beat Fallon, at 3.42%”), a number belonging to either will verify. The checker knows the number belongs to someone named in the sentence, but not which one the grammar attaches it to
"""