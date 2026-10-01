"""Shared helpers for Qwen topical/eligibility scoring. Gates: 114cce7.

2021/2022 only. Reorder the existing shortlist. Discard nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "trec"
REPORT = ROOT / "docs" / "trec_score.md"
THRESHOLDS_COMMIT = "114cce7"

SHORTLIST = DATA / "rerank_shortlists.json"
PACK = DATA / "score_pack.json"
QWEN_SCORES = DATA / "score_qwen.json"
MINI_SCORES = DATA / "score_mini_full.json"
OLD_MINI = DATA / "rerank_llm_scores.json"
CE_SCORES = DATA / "rerank_ce_scores.json"
RESULTS = DATA / "trec_score_results.json"

YEARS = (2021, 2022)
DEPTHS = (10, 20, 50, 100, 200, 500)
ELIG_SLICE_CHARS = 800
FULL_DEPTH = {2021: 1570, 2022: 1595}
RETRIEVAL_ELIGIBLE = {2021: 0.916, 2022: 0.914}

QWEN_MODEL = "Qwen/Qwen2.5-7B-Instruct"
MINI_MODEL = "gpt-4o-mini"
MINI_INPUT_USD = 0.15
MINI_OUTPUT_USD = 0.60
MINI_ARTICLE_CHARS = 1200

SAMPLE_SEED = 20261001
SAMPLE_TOPICS = {
    "2021": ["13", "18", "21", "23", "25", "27", "30", "31", "36", "37", "47", "51", "55", "70", "74"],
    "2022": ["10", "20", "21", "22", "23", "24", "25", "28", "29", "32", "35", "37", "41", "42", "50"],
}

# Verbatim scale from scripts/trec_rerank_llm.py. JSON return is kept for mini.
TOPICAL_SYSTEM = """You score how topically related a clinical-trial record is to a patient description.

This is not an eligibility decision. Do not say whether the patient can join the trial.
Score only whether the trial is about a disease, procedure, or situation that appears in the description.

Return only JSON: {"scores": [{"nct_id": "...", "score": 0}, ...]}
score is an integer 0, 1, 2, or 3.
0 = unrelated
1 = weakly related
2 = same disease area or a listed problem
3 = clearly about the main problem in the description"""

# Same scale wording. Output format is a single digit so logits can be read.
TOPICAL_SYSTEM_DIGIT = """You score how topically related a clinical-trial record is to a patient description.

This is not an eligibility decision. Do not say whether the patient can join the trial.
Score only whether the trial is about a disease, procedure, or situation that appears in the description.

score is an integer 0, 1, 2, or 3.
0 = unrelated
1 = weakly related
2 = same disease area or a listed problem
3 = clearly about the main problem in the description

Answer with a single digit: 0, 1, 2, or 3."""

ELIG_SYSTEM_DIGIT = """You judge whether a patient appears to meet a clinical trial's stated eligibility criteria.

This is not a decision that the patient qualifies. Do not say the patient can join the trial. The score is a ranking signal for a human who will read the criteria.

score is an integer 0, 1, 2, or 3.
0 = different disease or situation, or the stated criteria clearly rule this patient out
1 = right disease area, but one or more stated criteria probably fail
2 = right disease area, and the stated criteria look mostly compatible, with real remaining uncertainty
3 = the stated criteria look compatible with the description

If you cannot tell from the text, choose 2. Do not use 0 or 3 to express uncertainty. Uncertainty belongs in the middle of the scale.

Answer with a single digit: 0, 1, 2, or 3."""


def cond_list(row: dict) -> list[str]:
    raw = row.get("conditions") or []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    return [str(c).strip() for c in raw if str(c).strip()]


def title_cond_text(row: dict) -> str:
    title = (row.get("title") or "").strip()
    conds = "; ".join(cond_list(row))
    parts = [p for p in (title, f"Conditions: {conds}" if conds else "") if p]
    return "\n".join(parts) or " "


def title_cond_slice_text(row: dict) -> str:
    base = title_cond_text(row)
    elig = (row.get("eligibility") or "").strip()[:ELIG_SLICE_CHARS]
    if elig:
        return f"{base}\nEligibility (opening):\n{elig}"
    return base


def full_criteria_text(row: dict) -> str:
    base = title_cond_text(row)
    elig = (row.get("eligibility") or "").strip()
    if elig:
        return f"{base}\nEligibility criteria:\n{elig}"
    body = (row.get("text") or "").strip()
    if body:
        return f"{base}\nTrial text:\n{body}"
    return base


def trial_article_1200(row: dict) -> str:
    title = (row.get("title") or "").strip()
    body = (row.get("text") or "").strip()
    if title and body:
        text = f"{title}\n{body}"
    else:
        text = title or body or " "
    return text[:MINI_ARTICLE_CHARS]


def load_shortlist() -> dict:
    return json.loads(SHORTLIST.read_text(encoding="utf-8"))


def load_qrels(year: int) -> dict[str, dict[str, int]]:
    path = DATA / f"qrels{year}.txt"
    out: dict[str, dict[str, int]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) >= 4:
                out.setdefault(parts[0], {})[parts[2]] = int(parts[3])
    return out


def curve(order: list[str], labels: dict[str, int]) -> list[int]:
    hits = [0]
    n = 0
    for nct in order:
        if labels.get(nct) == 2:
            n += 1
        hits.append(n)
    return hits


def depth_for(hits: list[int], target: int) -> int:
    for i, val in enumerate(hits):
        if val >= target:
            return i
    return max(0, len(hits) - 1)


def mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None
