"""Pull recruiting NSCLC trials and test a plain word search.

The search that matches the 1,308 count in the spike brief is:

    GET https://clinicaltrials.gov/api/v2/studies
        query.cond = non-small cell lung cancer
        filter.overallStatus = RECRUITING

"NSCLC" is an abbreviation for non-small cell lung cancer. Searching the
abbreviation instead returns a different set, so this script does not use it.

The brief's 49-of-142 figure was measured on 300 of these trials. Those 300
identifiers were not saved, so this script measures every recruiting trial
the search returns today.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
JSONL_PATH = DATA_DIR / "nsclc_recruiting.jsonl"
META_PATH = DATA_DIR / "nsclc_recruiting_meta.json"
REPORT_PATH = DATA_DIR / "keyword_report.json"

API = "https://clinicaltrials.gov/api/v2/studies"
QUERY = {
    "query.cond": "non-small cell lung cancer",
    "filter.overallStatus": "RECRUITING",
    "fields": ",".join(
        [
            "NCTId",
            "BriefTitle",
            "OverallStatus",
            "Phase",
            "Condition",
            "EligibilityCriteria",
            "MinimumAge",
            "MaximumAge",
            "Sex",
            "HealthyVolunteers",
        ]
    ),
}

# The seven phrases named in the spike brief. Kept as one group so the
# measurement matches that writeup. Drug names and ordinary words are
# case-insensitive. Uppercase abbreviations stay case-sensitive.
IMMUNO_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("immunotherapy", re.compile(r"(?i)(?<![A-Za-z])immunotherapy(?![A-Za-z])")),
    ("PD-1", re.compile(r"(?<![A-Za-z0-9])PD-1(?![A-Za-z0-9])")),
    ("PD-L1", re.compile(r"(?<![A-Za-z0-9])PD-L1(?![A-Za-z0-9])")),
    ("checkpoint inhibitor", re.compile(r"(?i)checkpoint inhibitors?")),
    ("pembrolizumab", re.compile(r"(?i)(?<![A-Za-z])pembrolizumab(?![A-Za-z])")),
    ("nivolumab", re.compile(r"(?i)(?<![A-Za-z])nivolumab(?![A-Za-z])")),
    ("atezolizumab", re.compile(r"(?i)(?<![A-Za-z])atezolizumab(?![A-Za-z])")),
]

# Extra phrases counted on their own. They are not folded into the seven-term
# result. ICI is the known trap: the letters appear inside ordinary words.
EXTRA_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("durvalumab", re.compile(r"(?i)(?<![A-Za-z])durvalumab(?![A-Za-z])")),
    ("Keytruda", re.compile(r"(?i)(?<![A-Za-z])keytruda(?![A-Za-z])")),
    ("ICI as its own word", re.compile(r"(?<![A-Za-z])ICIs?(?![A-Za-z])")),
    ("ici letters anywhere, ignoring case", re.compile(r"(?i)ici")),
]

BRAIN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("brain metast", re.compile(r"(?i)brain metasta\w*")),
    ("brain mets", re.compile(r"(?i)(?<![A-Za-z])brain mets(?![A-Za-z])")),
    ("leptomeningeal", re.compile(r"(?i)leptomeningeal")),
    ("CNS metast", re.compile(r"(?i)(?<![A-Za-z])CNS metasta\w*")),
    ("central nervous system metast", re.compile(r"(?i)central nervous system metasta\w*")),
    ("intracranial", re.compile(r"(?i)(?<![A-Za-z])intracranial(?![A-Za-z])")),
    ("carcinomatous meningitis", re.compile(r"(?i)carcinomatous meningitis")),
]

INCLUSION_HEADER = re.compile(
    r"(?im)^[ \t]*(?:key[ \t]+)?inclusion[ \t]+criteria[ \t]*:?[ \t]*$"
)
EXCLUSION_HEADER = re.compile(
    r"(?im)^[ \t]*(?:key[ \t]+)?exclusion[ \t]+criteria[ \t]*:?[ \t]*$"
)
INCLUSION_LOOSE = re.compile(r"(?i)inclusion[ \t]+criteria")
EXCLUSION_LOOSE = re.compile(r"(?i)exclusion[ \t]+criteria")


def fetch_page(page_token: str | None) -> dict:
    params = dict(QUERY)
    params["pageSize"] = "1000"
    params["countTotal"] = "true"
    params["format"] = "json"
    if page_token:
        params["pageToken"] = page_token
    url = API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "ctgov-eligibility-spike"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def slim(study: dict) -> dict:
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    conditions = protocol.get("conditionsModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    return {
        "nct_id": ident.get("nctId"),
        "brief_title": ident.get("briefTitle"),
        "overall_status": status.get("overallStatus"),
        "phases": design.get("phases") or [],
        "conditions": conditions.get("conditions") or [],
        "minimum_age": eligibility.get("minimumAge"),
        "maximum_age": eligibility.get("maximumAge"),
        "sex": eligibility.get("sex"),
        "healthy_volunteers": eligibility.get("healthyVolunteers"),
        "eligibility_criteria": eligibility.get("eligibilityCriteria") or "",
    }


def download() -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    token = None
    total = None
    while True:
        payload = fetch_page(token)
        total = payload.get("totalCount", total)
        for study in payload.get("studies", []):
            records.append(slim(study))
        token = payload.get("nextPageToken")
        if not token:
            break
        time.sleep(0.2)
    meta = {
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "api": API,
        "query": QUERY,
        "reported_total": total,
        "saved_records": len(records),
    }
    with JSONL_PATH.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return records


def load() -> list[dict]:
    if not JSONL_PATH.exists():
        return download()
    records = []
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def split_sections(text: str) -> dict:
    """Return inclusion and exclusion text, plus how the header was found."""
    exclusion = EXCLUSION_HEADER.search(text)
    inclusion = INCLUSION_HEADER.search(text)
    if exclusion:
        cut = exclusion.start()
        return {
            "mode": "line_header",
            "inclusion": text[:cut],
            "exclusion": text[cut:],
            "exclusion_before_inclusion": bool(inclusion and inclusion.start() > cut),
        }
    loose_exclusion = EXCLUSION_LOOSE.search(text)
    loose_inclusion = INCLUSION_LOOSE.search(text)
    if loose_exclusion:
        cut = loose_exclusion.start()
        return {
            "mode": "loose_header",
            "inclusion": text[:cut],
            "exclusion": text[cut:],
            "exclusion_before_inclusion": bool(
                loose_inclusion and loose_inclusion.start() > cut
            ),
        }
    return {
        "mode": "no_header",
        "inclusion": text,
        "exclusion": "",
        "exclusion_before_inclusion": False,
    }


def hit_spans(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> list[int]:
    spans = []
    for _, pattern in patterns:
        spans.extend(match.start() for match in pattern.finditer(text))
    return spans


def classify(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> str:
    spans = hit_spans(text, patterns)
    if not spans:
        return "nowhere"
    parts = split_sections(text)
    if parts["mode"] == "no_header":
        return "unsplit"
    cut = len(parts["inclusion"])
    in_inclusion = any(span < cut for span in spans)
    in_exclusion = any(span >= cut for span in spans)
    if in_inclusion and in_exclusion:
        return "both"
    if in_exclusion:
        return "exclusion_only"
    return "inclusion_only"


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval for a proportion. Returns (point, low, high)."""
    if total == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom
    return (p, max(0.0, center - margin), min(1.0, center + margin))


def phrase_counts(records: list[dict], patterns: list[tuple[str, re.Pattern[str]]]) -> dict:
    counts = {}
    for name, pattern in patterns:
        counts[name] = sum(
            1 for record in records if pattern.search(record["eligibility_criteria"])
        )
    return counts


def summarize(records: list[dict], patterns: list[tuple[str, re.Pattern[str]]]) -> dict:
    buckets = Counter(classify(record["eligibility_criteria"], patterns) for record in records)
    hits = buckets["inclusion_only"] + buckets["exclusion_only"] + buckets["both"]
    # Brief definition: a keyword hit is "right" only when the phrase sits in
    # the exclusion section and not the inclusion section.
    narrow_right = buckets["exclusion_only"]
    # Wider definition: any mention in the exclusion section, including trials
    # that also mention the phrase in the inclusion section.
    wide_right = buckets["exclusion_only"] + buckets["both"]
    narrow = wilson(narrow_right, hits)
    wide = wilson(wide_right, hits)
    return {
        "buckets": dict(buckets),
        "keyword_hits": hits,
        "narrow_precision": {
            "right": narrow_right,
            "hits": hits,
            "point": narrow[0],
            "low": narrow[1],
            "high": narrow[2],
        },
        "wide_precision": {
            "right": wide_right,
            "hits": hits,
            "point": wide[0],
            "low": wide[1],
            "high": wide[2],
        },
    }


def barred_list_baseline(records: list[dict], patterns: list[tuple[str, re.Pattern[str]]]) -> dict:
    """Word search that looks only at the cannot-join section.

    A hit is a trial whose exclusion section contains any of the phrases.
    Scored against the section shortcut, precision is 1 by construction:
    the shortcut and the search use the same heading split. The useful
    numbers are how many whole-text hits this drops, and how many barred-list
    hits also mention the phrase on the required list.
    """
    buckets = Counter(classify(record["eligibility_criteria"], patterns) for record in records)
    anywhere_hits = buckets["inclusion_only"] + buckets["exclusion_only"] + buckets["both"]
    barred_hits = buckets["exclusion_only"] + buckets["both"]
    return {
        "whole_text_hits": anywhere_hits,
        "required_list_only": buckets["inclusion_only"],
        "barred_list_only": buckets["exclusion_only"],
        "both_lists": buckets["both"],
        "phrase_present_but_no_heading": buckets["unsplit"],
        "barred_list_search_hits": barred_hits,
        "whole_text_hits_dropped": buckets["inclusion_only"],
        "barred_list_hits_also_on_required_list": buckets["both"],
    }


HISTORY_PATTERNS = [item for item in IMMUNO_PATTERNS if item[0] not in {"PD-1", "PD-L1"}]
MARKER_PATTERNS = [item for item in IMMUNO_PATTERNS if item[0] in {"PD-1", "PD-L1"}]


def marker_versus_history(records: list[dict]) -> dict:
    """PD-1 and PD-L1 often name a lab result, not a prior drug.

    Counts how many whole-text hits match only those two phrases.
    """
    only_marker = 0
    history_word = 0
    for record in records:
        text = record["eligibility_criteria"]
        has_history = any(pattern.search(text) for _, pattern in HISTORY_PATTERNS)
        has_marker = any(pattern.search(text) for _, pattern in MARKER_PATTERNS)
        if has_history:
            history_word += 1
        elif has_marker:
            only_marker += 1
    return {
        "hits_with_a_history_word": history_word,
        "hits_with_only_pd1_or_pdl1": only_marker,
    }


def header_stats(records: list[dict]) -> dict:
    modes = Counter(split_sections(record["eligibility_criteria"])["mode"] for record in records)
    reversed_headers = sum(
        1
        for record in records
        if split_sections(record["eligibility_criteria"])["exclusion_before_inclusion"]
    )
    missing = sum(1 for record in records if not record["eligibility_criteria"].strip())
    lengths = [len(record["eligibility_criteria"]) for record in records]
    examples = []
    for record in records:
        if split_sections(record["eligibility_criteria"])["mode"] == "no_header":
            examples.append(
                {
                    "nct_id": record["nct_id"],
                    "preview": record["eligibility_criteria"][:240],
                }
            )
            if len(examples) == 8:
                break
    return {
        "header_modes": dict(modes),
        "exclusion_header_before_inclusion": reversed_headers,
        "missing_criteria": missing,
        "criteria_chars_total": sum(lengths),
        "criteria_chars_mean": (sum(lengths) / len(lengths)) if lengths else 0,
        "criteria_chars_max": max(lengths) if lengths else 0,
        "no_header_examples": examples,
    }


def main() -> None:
    records = load()
    report = {
        "n_records": len(records),
        "headers": header_stats(records),
        "immuno_phrase_docs": phrase_counts(records, IMMUNO_PATTERNS),
        "extra_phrase_docs": phrase_counts(records, EXTRA_PATTERNS),
        "brain_phrase_docs": phrase_counts(records, BRAIN_PATTERNS),
        "immuno_seven_terms": summarize(records, IMMUNO_PATTERNS),
        "brain_any_listed_phrase": summarize(records, BRAIN_PATTERNS),
        "immuno_barred_list_baseline": barred_list_baseline(records, IMMUNO_PATTERNS),
        "brain_barred_list_baseline": barred_list_baseline(records, BRAIN_PATTERNS),
        "immuno_marker_versus_history": marker_versus_history(records),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
