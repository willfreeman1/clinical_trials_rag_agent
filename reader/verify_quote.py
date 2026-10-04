"""Categorise a quoted span. Not a raw match test.

The earlier lung-cancer checker flagged 52% of quotes. Almost all of
that was benign. After sorting the flags:

- A — stitched from two real passages (45.8% of flags)
- B — whitespace or punctuation only (0.2%)
- C — real passage, word-list miss (49.9%)
- D — paraphrased (1.0%)
- E — absent from the source (3.2%)

Only D and E are fabrication. This module reports the same buckets.
C here means: the span is in the named source, but it is not about
this rule (almost no shared content words with the rule text). There
is no topic word-list on TREC rules.

A flagged quote is kept. The rejection rate is a signal.

The system does not say a patient qualifies.
"""

from __future__ import annotations

import re

from reader.schema import Rule, RuleJudgement

_PUNCT = {
    "\u00a0": " ",
    "–": "-",
    "—": "-",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "≤": "<=",
    "≥": ">=",
    "×": "x",
    "µ": "u",
    "μ": "u",
}


def normalize_basic(value: str) -> str:
    value = (value or "").replace("\\", "").replace("*", "")
    return re.sub(r"\s+", " ", value).strip()


def normalize_strong(value: str) -> str:
    text = normalize_basic(value).lower()
    for src, dst in _PUNCT.items():
        text = text.replace(src, dst)
    text = re.sub(r"^[\s\-\*\u2022\d.]+", "", text)
    text = re.sub(r"[^\w\s=<>]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _present_basic(quote: str, text: str) -> bool:
    if not quote.strip():
        return False
    if quote in text:
        return True
    return bool(normalize_basic(quote)) and normalize_basic(quote) in normalize_basic(text)


def _present_strong(quote: str, text: str) -> bool:
    if not quote.strip():
        return False
    sq, st = normalize_strong(quote), normalize_strong(text)
    return bool(sq) and sq in st


def _split_parts(quote: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+|\s*[;•]\s+|\s+\*\s+|\n+", quote)
    parts = [p.strip(" -\t") for p in raw if len(p.strip()) >= 15]
    if len(parts) < 2:
        parts = [p.strip() for p in re.split(r"\s+and\s+(?=[A-Z*])", quote) if len(p.strip()) >= 15]
    return parts


def _is_stitched(quote: str, text: str) -> bool:
    if _present_strong(quote, text):
        return False
    parts = _split_parts(quote)
    if len(parts) < 2:
        return False
    hits = [p for p in parts if _present_strong(p, text)]
    return len(hits) >= 2


def _content_words(value: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", value or "")]


def _in_order_ratio(quote: str, text: str) -> float:
    need = _content_words(quote)
    if len(need) < 6:
        return 0.0
    hay = _content_words(text)
    i = 0
    for word in hay:
        if i < len(need) and word == need[i]:
            i += 1
    return i / len(need)


def _overlap(a: str, b: str) -> float:
    wa, wb = set(_content_words(a)), set(_content_words(b))
    if len(wa) < 3 or not wb:
        return 0.0
    return len(wa & wb) / len(wa)


def bucket_quote(quote: str, source_text: str, rule_text: str, quote_source: str) -> str:
    quote = quote or ""
    if not quote.strip():
        return "E"
    basic = _present_basic(quote, source_text)
    strong = _present_strong(quote, source_text)
    if basic or strong:
        words = _content_words(quote)
        if quote_source == "trial" and len(words) >= 3 and _overlap(quote, rule_text) < 0.20:
            return "C"
        if basic:
            return "ok"
        return "B"
    if _is_stitched(quote, source_text):
        return "A"
    if _in_order_ratio(quote, source_text) >= 0.85:
        return "D"
    return "E"


def verify_judgement(
    judgement: RuleJudgement,
    rule: Rule,
    patient_note: str,
    trial_text: str,
) -> RuleJudgement:
    source = patient_note if judgement.quote_source == "patient" else trial_text
    bucket = bucket_quote(judgement.quote, source, rule.text, judgement.quote_source)
    judgement.quote_bucket = bucket
    judgement.quote_flagged = bucket != "ok"
    return judgement


def fabrication(bucket: str) -> bool:
    return bucket in {"D", "E"}
