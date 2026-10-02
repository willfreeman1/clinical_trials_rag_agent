"""Shared Step 8 helpers. Design committed in step8_design.json before any run."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from mini_pilot import normalize_for_match, quote_match  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "step8_design.json").read_text(encoding="utf-8"))
DATA = ROOT / "data"

EXPENSIVE = DESIGN["expensive_model"]
CHEAP = DESIGN["cheap_model"]
PRICES = {
    EXPENSIVE: DESIGN["expensive_usd_per_million"],
    CHEAP: DESIGN["cheap_usd_per_million"],
}

OVERALL = (
    "definitely_excluded",
    "candidate_needs_human_check",
    "never_eligible",
)
RULE_VERDICTS = (
    "excludes_this_patient",
    "does_not_exclude",
    "not_enough_information",
)

IMMUNO_WORDS = re.compile(
    r"immunotherapy|checkpoint inhibitor|pembrolizumab|nivolumab|atezolizumab|"
    r"durvalumab|ipilimumab|anti-PD-1|anti-PD-L1|\bPD-1\b|\bPD-L1\b|\bCTLA-4\b",
    re.IGNORECASE,
)
BRAIN_WORDS = re.compile(
    r"brain|central nervous system|\bCNS\b|leptomeningeal|intracranial|"
    r"carcinomatous meningitis",
    re.IGNORECASE,
)
PLATINUM_WORDS = re.compile(
    r"platinum|cisplatin|carboplatin|oxaliplatin|nedaplatin",
    re.IGNORECASE,
)
CHEMO_WORDS = re.compile(r"chemotherap", re.IGNORECASE)
SYSTEMIC_WORDS = re.compile(r"systemic", re.IGNORECASE)
AUTOIMMUNE_WORDS = re.compile(
    r"autoimmune|rheumatoid|lupus|\bIBD\b|inflammatory bowel|colitis|psoriasis",
    re.IGNORECASE,
)
STAGE_WORDS = re.compile(
    r"\bstage\b|metastatic|locally advanced|unresectable|\bIIIB\b|\bIV\b",
    re.IGNORECASE,
)
MARKER_WORDS = re.compile(
    r"EGFR|ALK|KRAS|ROS1|BRAF|\bMET\b|\bRET\b|NTRK|HER2|ERBB2|"
    r"mutation|fusion|rearrangement|wild[\s-]?type|driver|biomarker|NGS",
    re.IGNORECASE,
)

TOPIC_WORDS = {
    "previous immunotherapy": IMMUNO_WORDS,
    "previous platinum chemotherapy": PLATINUM_WORDS,
    "previous chemotherapy (any kind)": CHEMO_WORDS,
    "previous systemic anticancer treatment (any kind)": SYSTEMIC_WORDS,
    "cancer spread to the brain": BRAIN_WORDS,
    "autoimmune disease": AUTOIMMUNE_WORDS,
    "disease stage": STAGE_WORDS,
    "tumour genetic marker": MARKER_WORDS,
    "tumor genetic marker": MARKER_WORDS,
}

FACT_TO_KEY = {
    "previous immunotherapy": "prior_immunotherapy",
    "cancer spread to the brain": "brain_metastases",
    "tumour genetic marker": "driver_mutation",
    "tumor genetic marker": "driver_mutation",
    "previous platinum chemotherapy": "prior_platinum_chemo",
    "autoimmune disease": "autoimmune_disease",
    "disease stage": "disease_stage",
}


def wilson(successes: int, total: int, z: float = 1.96) -> dict | None:
    if total == 0:
        return None
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom
    out = {
        "point": round(p, 4),
        "low": round(max(0.0, center - margin), 4),
        "high": round(min(1.0, center + margin), 4),
        "n": total,
        "k": successes,
    }
    if total >= 200:
        out["wilson_omitted_n_ge_200"] = True
        out.pop("low", None)
        out.pop("high", None)
    return out


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICES[model]
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


def load_trials() -> dict[str, dict]:
    from keyword_section_check import JSONL_PATH

    found = {}
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            found[row["nct_id"]] = row
    return found


def canonical_fact(raw: str) -> str:
    text = " ".join((raw or "").strip().lower().split()).replace("tumor", "tumour")
    aliases = {
        "previous immunotherapy": "previous immunotherapy",
        "previous checkpoint inhibitor": "previous immunotherapy",
        "cancer spread to the brain": "cancer spread to the brain",
        "tumour genetic marker": "tumour genetic marker",
        "previous platinum chemotherapy": "previous platinum chemotherapy",
        "previous chemotherapy (any kind)": "previous chemotherapy (any kind)",
        "previous chemotherapy": "previous chemotherapy (any kind)",
        "previous systemic anticancer treatment (any kind)": "previous systemic anticancer treatment (any kind)",
        "previous systemic anticancer treatment": "previous systemic anticancer treatment (any kind)",
        "previous anticancer therapy of any kind": "previous anticancer therapy of any kind",
        "previous anticancer therapy": "previous anticancer therapy of any kind",
        "autoimmune disease": "autoimmune disease",
        "disease stage": "disease stage",
    }
    return aliases.get(text, text)


def topic_ok(fact: str, quote: str) -> bool | None:
    """True/False if we have a keyword list; None if the fact is open."""
    words = TOPIC_WORDS.get(canonical_fact(fact))
    if words is None:
        return None
    return bool(words.search(quote or ""))


def quote_status(quote: str, trial_text: str) -> str:
    if not (quote or "").strip():
        return "empty"
    return quote_match(quote, trial_text)
